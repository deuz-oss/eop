import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from eop_api.dependencies.auth import CurrentUser
from eop_api.schemas.file import FileResponse
from eop_api.services.file import FileService

router = APIRouter(prefix="/files", tags=["Files"])


def get_file_service() -> FileService:
    return FileService()


FileServiceDep = Annotated[FileService, Depends(get_file_service)]


def _file_size(file: UploadFile) -> int:
    """`UploadFile.size` is normally populated by the multipart parser; fall back
    to measuring the spooled file directly if a client omitted it."""
    if file.size is not None:
        return file.size
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    return size


@router.post("", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    service: FileServiceDep,
    _: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> FileResponse:
    file_object = await service.upload(
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size=_file_size(file),
        data=file.file,
    )
    return FileResponse.model_validate(file_object)


@router.get("/{file_id}")
async def download_file(
    file_id: uuid.UUID, service: FileServiceDep, _: CurrentUser
) -> StreamingResponse:
    result = await service.download(file_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_object, stream = result
    return StreamingResponse(
        stream,
        media_type=file_object.content_type,
        headers={"Content-Disposition": f'attachment; filename="{file_object.filename}"'},
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: uuid.UUID, service: FileServiceDep, _: CurrentUser) -> None:
    deleted = await service.delete(file_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
