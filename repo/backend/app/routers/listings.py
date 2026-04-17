from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.models.listing import Listing, ListingMedia
from app.models.media import Media
from app.models.property import Unit
from app.models.resident import Resident
from app.models.user import User
from app.services.audit_service import log_audit
from app.schemas.listing import (
    BulkStatusRequest,
    BulkStatusResponse,
    BulkStatusResult,
    ListingCreate,
    ListingListResponse,
    ListingResponse,
    ListingStatusUpdate,
    ListingUpdate,
)

router = APIRouter(prefix="/listings", tags=["listings"])


async def _listing_to_response(db: AsyncSession, listing: Listing) -> ListingResponse:
    data = ListingResponse.model_validate(listing).model_dump()
    media_ids = [link.media_id for link in (listing.media_links or [])]
    media_map: dict[str, Media] = {}
    if media_ids:
        media_result = await db.execute(select(Media).where(Media.id.in_(media_ids)))
        media_map = {str(m.id): m for m in media_result.scalars().all()}
    data["media"] = [
        {
            "media_id": link.media_id,
            "sort_order": link.sort_order,
            "filename": media_map.get(str(link.media_id)).original_name if media_map.get(str(link.media_id)) else None,
            "mime_type": media_map.get(str(link.media_id)).mime_type if media_map.get(str(link.media_id)) else None,
            "file_url": f"/api/v1/media/{link.media_id}/file",
        }
        for link in (listing.media_links or [])
    ]
    return ListingResponse.model_validate(data)


@router.get("/", response_model=ListingListResponse)
async def list_listings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    property_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Listing)

    # Residents can only see published listings scoped to their property
    if current_user.role == "resident":
        resident_result = await db.execute(
            select(Resident).where(Resident.user_id == current_user.id)
        )
        resident = resident_result.scalars().first()
        if resident:
            unit_result = await db.execute(
                select(Unit).where(Unit.id == resident.unit_id)
            )
            unit = unit_result.scalars().first()
            if unit:
                query = query.where(Listing.property_id == unit.property_id)
        query = query.where(Listing.status == "published")
    elif status_filter:
        query = query.where(Listing.status == status_filter)

    if category:
        query = query.where(Listing.category == category)
    if property_id:
        query = query.where(Listing.property_id == property_id)

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Listing.created_at.desc()).offset(offset).limit(page_size)
    )
    listings = result.scalars().all()

    items = [await _listing_to_response(db, lst) for lst in listings]
    return ListingListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    body: ListingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager")),
):
    listing = Listing(
        property_id=body.property_id,
        title=body.title,
        description=body.description,
        category=body.category,
        price=body.price,
        status="draft",
        created_by=current_user.id,
    )
    db.add(listing)
    await db.flush()
    await log_audit(db, user_id=current_user.id, action="CREATE", resource_type="listing", resource_id=listing.id, new_value={"title": listing.title, "category": listing.category})
    await db.commit()
    await db.refresh(listing)
    return await _listing_to_response(db, listing)


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalars().first()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )
    # Residents can only view published listings
    if current_user.role == "resident" and listing.status != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Listing not available"
        )
    return await _listing_to_response(db, listing)


@router.put("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: UUID,
    body: ListingUpdate,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalars().first()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )

    update_data = body.model_dump(exclude_unset=True)

    if str(listing.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(listing, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=listing.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    for field, value in update_data.items():
        setattr(listing, field, value)

    listing.version += 1
    listing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(listing)
    return await _listing_to_response(db, listing)


@router.put("/{listing_id}/status", response_model=ListingResponse)
async def update_listing_status(
    listing_id: UUID,
    body: ListingStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalars().first()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )

    if str(listing.version) != if_match:
        client_version = int(if_match)
        update_data = body.model_dump(exclude_unset=True)
        server_data_dict = {field: getattr(listing, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=listing.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    old_status = listing.status
    listing.status = body.status

    # Set published_at when publishing, clear when unpublishing
    if body.status == "published" and old_status != "published":
        listing.published_at = datetime.now(timezone.utc)
    elif body.status == "unpublished":
        listing.published_at = None

    listing.version += 1
    listing.updated_at = datetime.now(timezone.utc)
    await log_audit(db, user_id=current_user.id, action="UPDATE_STATUS", resource_type="listing", resource_id=listing.id, old_value={"status": old_status}, new_value={"status": body.status})
    await db.commit()
    await db.refresh(listing)
    return await _listing_to_response(db, listing)


@router.post("/bulk-status", response_model=BulkStatusResponse)
async def bulk_update_status(
    body: BulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager")),
):
    results: list[BulkStatusResult] = []
    updated_count = 0
    failed_count = 0

    for listing_id in body.listing_ids:
        result = await db.execute(select(Listing).where(Listing.id == listing_id))
        listing = result.scalars().first()
        if not listing:
            results.append(BulkStatusResult(id=listing_id, status="not_found", success=False))
            failed_count += 1
            continue

        old_status = listing.status
        listing.status = body.status
        if body.status == "published" and old_status != "published":
            listing.published_at = datetime.now(timezone.utc)
        elif body.status == "unpublished":
            listing.published_at = None

        listing.version += 1
        listing.updated_at = datetime.now(timezone.utc)
        results.append(BulkStatusResult(id=listing_id, status=body.status, success=True))
        updated_count += 1

    await db.commit()
    return BulkStatusResponse(updated=updated_count, failed=failed_count, results=results)
