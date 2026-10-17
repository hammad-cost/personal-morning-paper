from pydantic import BaseModel, Field, field_validator


class OnboardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    paper_title: str | None = Field(default=None, max_length=80)
    bio: str = Field(default="", max_length=280)
    topic_weights: dict[str, int] = Field(default_factory=dict)

    @field_validator("name", "bio")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("topic_weights")
    @classmethod
    def clean_topics(cls, value: dict[str, int]) -> dict[str, int]:
        return {topic.strip(): weight for topic, weight in value.items() if topic.strip()}


class UserProfile(BaseModel):
    onboarded: bool = False
    name: str = ""
    paper_title: str = ""
    bio: str = ""
    topic_weights: dict[str, int] = Field(default_factory=dict)
    source_weights: dict[str, int] = Field(default_factory=dict)
    created_at: str | None = None


class StateResponse(BaseModel):
    onboarded: bool
    profile: UserProfile
    today_edition_id: str | None
