import uuid as uuid_mod
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.models.order import Order, OrderMilestone, ORDER_TRANSITIONS
from app.models.resident import Resident
from app.models.user import User
from app.schemas.order import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderTransitionRequest,
    OrderUpdate,
    MilestoneResponse,
)
from app.middleware.idempotency import check_idempotency, store_idempotency
from app.services.order_service import validate_transition, transition_order
from app.services.audit_service import log_audit

router = APIRouter(prefix="/orders", tags=["orders"])

# Role permissions per transition (from design.md Section 9.2)
TRANSITION_ROLES: dict[str, set[str]] = {
    "payment_recorded": {"resident", "accounting_clerk", "admin"},
    "accepted": {"property_manager", "accounting_clerk", "admin"},
    "dispatched": {"property_manager", "maintenance_dispatcher", "admin"},
    "arrived": {"maintenance_dispatcher", "admin"},
    "in_service": {"maintenance_dispatcher", "admin"},
    "completed": {"maintenance_dispatcher", "admin"},
    "after_sales_credit": {"property_manager", "accounting_clerk", "admin"},
}


# -- Helpers -------------------------------------------------------------------

async def _get_order_or_404(db: AsyncSession, order_id: UUID) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


async def _get_resident_for_user(db: AsyncSession, user_id: UUID) -> Resident:
    result = await db.execute(select(Resident).where(Resident.user_id == user_id))
    resident = result.scalars().first()
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No resident profile found for current user",
        )
    return resident


# -- List orders ---------------------------------------------------------------

@router.get("/", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    resident_id: UUID | None = Query(None),
    assigned_to: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Order)

    # Residents can only see their own orders
    if current_user.role == "resident":
        res = await _get_resident_for_user(db, current_user.id)
        query = query.where(Order.resident_id == res.id)
    else:
        if resident_id:
            query = query.where(Order.resident_id == resident_id)
        if assigned_to:
            query = query.where(Order.assigned_to == assigned_to)

    if status_filter:
        query = query.where(Order.status == status_filter)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Order.created_at.desc()).offset(offset).limit(page_size)
    )
    orders = result.scalars().all()

    return OrderListResponse(
        items=[OrderResponse.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


# -- Create order with idempotency --------------------------------------------

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check idempotency via persistent store
    existing_idem = await check_idempotency(db, body.idempotency_key)
    if existing_idem and existing_idem.response_body:
        return OrderResponse.model_validate(existing_idem.response_body)

    # Idempotency check: if an order with this key already exists, return it
    existing = await db.execute(
        select(Order).where(Order.idempotency_key == body.idempotency_key)
    )
    existing_order = existing.scalars().first()
    if existing_order:
        return OrderResponse.model_validate(existing_order)

    # Resolve resident context: residents use their own profile; staff must supply resident_id
    if current_user.role == "resident":
        resident = await _get_resident_for_user(db, current_user.id)
    else:
        if not body.resident_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Staff must provide resident_id when creating orders",
            )
        res_result = await db.execute(select(Resident).where(Resident.id == body.resident_id))
        resident = res_result.scalars().first()
        if not resident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resident not found",
            )

    order = Order(
        resident_id=resident.id,
        property_id=body.property_id,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        status="created",
        idempotency_key=body.idempotency_key,
    )
    db.add(order)
    await db.flush()

    # Record the initial "created" milestone
    milestone = OrderMilestone(
        order_id=order.id,
        from_status=None,
        to_status="created",
        changed_by=current_user.id,
        notes="Order created",
    )
    db.add(milestone)

    await log_audit(
        db, user_id=current_user.id, action="CREATE",
        resource_type="order", resource_id=order.id,
        new_value={"status": "created", "title": order.title},
    )

    response = OrderResponse.model_validate(order)
    await store_idempotency(
        db, body.idempotency_key, current_user.id,
        "/orders", 201, response.model_dump(mode="json"),
    )

    await db.commit()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


# -- Get order detail ----------------------------------------------------------

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await _get_order_or_404(db, order_id)

    # Residents can only view their own orders
    if current_user.role == "resident":
        res = await _get_resident_for_user(db, current_user.id)
        if order.resident_id != res.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return OrderResponse.model_validate(order)


# -- Update order metadata (staff) ---------------------------------------------

@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: UUID,
    body: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager", "maintenance_dispatcher")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    order = await _get_order_or_404(db, order_id)

    update_data = body.model_dump(exclude_unset=True)

    if str(order.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(order, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=order.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    for field, value in update_data.items():
        setattr(order, field, value)

    order.version += 1
    order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


# -- Transition order state ----------------------------------------------------

@router.post("/{order_id}/transition", response_model=OrderResponse)
async def transition_order_endpoint(
    order_id: UUID,
    body: OrderTransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for state transitions",
        )

    order = await _get_order_or_404(db, order_id)

    # Idempotency: check persistent store by explicit request key
    existing_idem = await check_idempotency(db, body.idempotency_key)
    if existing_idem and existing_idem.response_body:
        return OrderResponse.model_validate(existing_idem.response_body)

    # Secondary idempotency: if this milestone already exists, return current state
    existing_milestone = await db.execute(
        select(OrderMilestone).where(
            OrderMilestone.order_id == order_id,
            OrderMilestone.to_status == body.to_status,
        )
    )
    if existing_milestone.scalars().first():
        return OrderResponse.model_validate(order)

    if if_match is not None and str(order.version) != if_match:
        client_version = int(if_match)
        update_data = body.model_dump(exclude_unset=True)
        server_data_dict = {field: getattr(order, field) for field in update_data.keys() if hasattr(order, field)}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=order.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    # Validate transition is allowed by state machine
    if not validate_transition(order.status, body.to_status):
        allowed = ORDER_TRANSITIONS.get(order.status, [])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_transition",
                "message": f"Cannot transition from '{order.status}' to '{body.to_status}'",
                "current_status": order.status,
                "requested_status": body.to_status,
                "allowed_transitions": allowed,
            },
        )

    # Role-based permission check for this specific transition
    allowed_roles = TRANSITION_ROLES.get(body.to_status, {"admin"})
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role}' cannot perform transition to '{body.to_status}'",
        )

    # Business rule: dispatched requires assigned_to
    if body.to_status == "dispatched" and not order.assigned_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order must have an assigned technician before dispatching",
        )

    old_status = order.status
    order = await transition_order(
        db=db,
        order=order,
        to_status=body.to_status,
        user_id=current_user.id,
        notes=body.notes,
    )

    await log_audit(
        db, user_id=current_user.id, action="STATE_CHANGE",
        resource_type="order", resource_id=order.id,
        old_value={"status": old_status},
        new_value={"status": body.to_status},
    )

    response = OrderResponse.model_validate(order)
    await store_idempotency(
        db, body.idempotency_key, current_user.id,
        f"/orders/{order_id}/transition", 200, response.model_dump(mode="json"),
    )

    await db.commit()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


# -- Milestones history --------------------------------------------------------

@router.get("/{order_id}/milestones")
async def get_order_milestones(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await _get_order_or_404(db, order_id)

    # Residents can only view milestones for their own orders
    if current_user.role == "resident":
        res = await _get_resident_for_user(db, current_user.id)
        if order.resident_id != res.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(OrderMilestone)
        .where(OrderMilestone.order_id == order_id)
        .order_by(OrderMilestone.created_at.asc())
    )
    milestones = result.scalars().all()

    return {
        "order_id": str(order_id),
        "status": order.status,
        "milestones": [MilestoneResponse.model_validate(m).model_dump() for m in milestones],
    }
