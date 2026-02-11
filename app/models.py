from typing import Optional
from sqlmodel import Field, SQLModel
import uuid

from sqlalchemy import Column, JSON
from typing import List

class PersonaBase(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    personality: str
    style: str
    system_prompt: Optional[str] = None
    allowed_tools: List[str] = Field(default=[], sa_column=Column(JSON))

class Persona(PersonaBase, table=True):
    __tablename__ = "konex_personas"

class PersonaCreate(PersonaBase):
    pass

class PersonaRead(PersonaBase):
    pass

class PersonaUpdate(SQLModel):
    name: Optional[str] = None
    personality: Optional[str] = None
    style: Optional[str] = None
    system_prompt: Optional[str] = None
    allowed_tools: Optional[List[str]] = None

class KnowledgeItemBase(SQLModel):
    title: str = Field(index=True)
    content: str
    source_uri: Optional[str] = None
    
class KnowledgeItem(KnowledgeItemBase, table=True):
    __tablename__ = "konex_knowledge_items"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: int = Field(default_factory=lambda: 0) # Placeholder, ideally use datetime
    updated_at: int = Field(default_factory=lambda: 0)

class KnowledgeItemCreate(KnowledgeItemBase):
    pass

class KnowledgeItemRead(KnowledgeItemBase):
    id: str
    created_at: int
    updated_at: int

class Admin(SQLModel, table=True):
    __tablename__ = "konex_admins"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_phone: str = Field(index=True)     # Who is the admin?
    channel_phone: str = Field(index=True)  # Which channel do they manage?
    permissions: str = Field(default="*")   # JSON list of allowed commands or "*"
    created_by: Optional[str] = None        # Who granted this?
    created_at: int = Field(default_factory=lambda: 0)

class ChannelConfig(SQLModel, table=True):
    __tablename__ = "konex_channel_configs"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    channel_phone: str = Field(index=True, unique=True)
    persona_id: str = Field(foreign_key="konex_personas.id")
    knowledge_base_id: Optional[str] = None 
    system_prompt_override: Optional[str] = None

