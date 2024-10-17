import hashlib
import json
import mimetypes
import os
import boto3
import re
from fastapi import HTTPException
from openg2p_fastapi_common.service import BaseService
from openg2p_portal_api.models.document_file import DocumentFile  
from openg2p_portal_api.models.orm.document_store_orm import DocumentStoreORM
from openg2p_portal_api.models.orm.document_tag_orm import DocumentTagORM
from openg2p_portal_api.models.orm.program_orm import ProgramORM
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from ..models.orm.document_file_orm import DocumentFileORM
from openg2p_fastapi_common.context import dbengine
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi import HTTPException
from botocore.exceptions import ClientError
import logging
_logger = logging.getLogger(__name__)


class DocumentFileService(BaseService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.async_session_maker = async_sessionmaker(dbengine.get())

    async def get_document_by_id(self, document_id: int):
        """
        Retrieve a document from the database by its ID.
        """
        async with self.async_session_maker() as session:
            try:
                result = await session.execute(
                    select(DocumentFileORM).where(DocumentFileORM.id == document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    raise Exception("Document not found")

                return DocumentFile.from_orm(document)  
            except SQLAlchemyError as e:
                raise Exception("Error retrieving document: " + str(e))


    async def upload_document(self,programid: int,name: str, data: bytes,file_tag:str):
        """
        Upload a document, save metadata in the database, and return the saved document object.
        """
        async with self.async_session_maker() as session:
            
            if data is None:
                raise HTTPException(status_code=400, detail="Content must not be None.")
            
            company_id, backend_id = await self.get_company_and_backend_id_by_programid(programid)

            filename=name 
            extension = os.path.splitext(name)
            mimetype = mimetypes.guess_type(name)[0] or ""
            checksum = hashlib.sha1(data).hexdigest()
            
            new_file = DocumentFileORM(
            name=name,
            backend_id=backend_id,
            file_size=len(data),
            checksum=checksum,
            filename=filename,
            extension=extension,
            mimetype=mimetype,
            company_id=company_id,
            active=True
            )
            self.extract_filename(new_file)
            self.compute_human_file_size(new_file)

            new_file.relative_path = await self.build_relative_path(new_file, checksum)
            new_file.write_uid = await self.get_tag_id_by_name(file_tag)

            session.add(new_file)
            await session.commit() 
            await session.refresh(new_file) 
            
            return DocumentFile.from_orm(new_file) 
    

    async def upload_document_minio(self, file_obj, file_name: str, programid: int):
        """
        Upload a document to MinIO storage and update its database record with the slug and relative path.
        """
        async with self.async_session_maker() as session:
    
            if file_obj is None:
                raise ValueError("The file object is empty or not readable.")   
            
            if not hasattr(file_obj, 'seek'):
                raise ValueError("The file object is not seekable.")
            file_obj.seek(0)

            # Convert file name to a URL-friendly slug
            original_filename = file_name
            slugified_filename = slugify(original_filename)
            file_id = await self.get_file_id_by_slug()
            final_filename = f"{slugified_filename}-{file_id}"
            company_id,backend_id = await self.get_company_and_backend_id_by_programid(programid)

            # Fetch backend configuration from DocumentStoreORM based on backend_id
            if not backend_id:
                raise ValueError(f"Invalid backend_id: {backend_id}")
            
            result = await session.execute(
                select(DocumentStoreORM).filter_by(id=backend_id)
            )
            backend = result.scalars().first()
            
            if not backend or not backend.server_env_defaults:
                raise ValueError(f"The backend {backend_id} is invalid or does not exist.")

            # Parse server_env_defaults if it's a string
            if isinstance(backend.server_env_defaults, str):
                try:
                    backend.server_env_defaults = json.loads(backend.server_env_defaults)
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON format in server_env_defaults.")
                
            endpoint_url = backend.server_env_defaults.get("x_aws_host_env_default")
            aws_access_key = backend.server_env_defaults.get("x_aws_access_key_id_env_default")
            aws_secret_key = backend.server_env_defaults.get("x_aws_secret_access_key_env_default")
            region_name = backend.server_env_defaults.get("x_aws_region_env_default")
            bucket_name = backend.server_env_defaults.get("x_aws_bucket_env_default")

            # Initialize the S3 client
            try:
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=endpoint_url,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=region_name  
                )
                self.bucket_name = bucket_name
            except Exception as e:
                raise ValueError(f"Failed to initialize S3 client: {str(e)}")

            try:
                # Upload the file to S3 (MinIO)
                self.s3_client.upload_fileobj(file_obj, self.bucket_name, final_filename)
                # Update the slug and relative path in the database
                await self.update_slug_relative_path(file_id, final_filename)
            except ClientError as e:
                _logger.error(f"Error uploading file {file_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
            except Exception as e:
                _logger.error(f"Unexpected error while uploading file {file_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))


    async def get_company_and_backend_id_by_programid(self, programid: int):
        """
        Fetch the company_id and backend_id from the ProgramORM using the provided programid.
        """
        async with self.async_session_maker() as session:
            result = await session.execute(
                select(ProgramORM).filter_by(id=programid)
            )
            program = result.scalars().first()
            if program:
                return program.company_id, program.supporting_documents_store
            else:
                return None, None


    async def get_file_id_by_slug(self):
        """
        Update the document's slug and relative path in the database after it is uploaded.
        """
        async with self.async_session_maker() as session:
            result = await session.execute(
                select(DocumentFileORM)
                .where(DocumentFileORM.slug == None)
                .order_by(DocumentFileORM.id.desc())  
                .limit(1)
            )
            document_file = result.scalars().first()
            if document_file:
                return document_file.id  
            else:
                return None


    async def update_slug_relative_path(self, file_id: int, slug: str):
        async with self.async_session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    select(DocumentFileORM).where(DocumentFileORM.id == file_id)
                )
                document_file = result.scalars().first()
                if document_file:
                    document_file.slug = slug
                    document_file.relative_path = slug
                    await session.commit()
                else:
                    raise ValueError(f"Document file with ID {file_id} not found.")
                
    def slugify(value: str) -> str:
        """
        Convert a string to a slug: lowercase, replace spaces with dashes, and remove non-alphanumeric characters.
        """
        value = value.lower()
        value = re.sub(r'\s+', '-', value)  
        value = re.sub(r'[^a-z0-9-]', '', value) 
        value = value.strip('-') 
        return value
    
    async def get_tag_id_by_name(self, tag_name: str) -> int:
        async with self.async_session_maker() as session:  
            try:
                result = await session.execute(
                    select(DocumentTagORM.create_uid).where(DocumentTagORM.name == tag_name)
                )
                tag_id = result.scalars().first()  
                if tag_id is None:
                    raise HTTPException(status_code=404, detail=f"Tag '{tag_name}' not found.")
                return tag_id
            except SQLAlchemyError as e:
                raise HTTPException(status_code=500, detail=f"Error retrieving tag: {str(e)}")



    async def build_relative_path(self, document_file: DocumentFileORM, checksum: str) -> str:
        """
        Build the relative path for the uploaded document based on the filename strategy in the backend settings.
        """
        async with self.async_session_maker() as session:
            result = await session.execute(
                select(DocumentStoreORM).filter_by(id=document_file.backend_id)
            )
            backend = result.scalars().first()
            
            if not backend or not backend.server_env_defaults:
                raise ValueError(f"The backend {document_file.backend_id} is invalid or does not exist.")

            if isinstance(backend.server_env_defaults, str):
                try:
                    backend.server_env_defaults = json.loads(backend.server_env_defaults)
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON format in server_env_defaults.")

            filename_strategy = backend.server_env_defaults.get("x_filename_strategy_env_default", "default_strategy")

            if filename_strategy == "hash":
                return f"{checksum[:2]}/{checksum}"
            elif filename_strategy == "name_with_id":
                return document_file.slug
            else:
                raise ValueError(f"Unknown filename strategy: {filename_strategy}")



    def compute_human_file_size(self, document_file: DocumentFileORM):
        """Compute human-readable file size."""
        if document_file.file_size is not None:
            document_file.human_file_size = self.human_size(document_file.file_size)

    def human_size(self, size: int) -> str:
        """Convert bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    

    def extract_filename(self, document_file: DocumentFileORM):
        """Extract filename and extension from name."""
        if document_file.name:
            document_file.filename, document_file.extension = os.path.splitext(document_file.name)
            document_file.mimetype = mimetypes.guess_type(document_file.name)[0] or ""
