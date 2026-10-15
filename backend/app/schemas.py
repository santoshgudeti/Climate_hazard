from typing import Literal
from pydantic import BaseModel, Field, model_validator


class HeatwaveRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str = Field(min_length=1, max_length=120)
    start_year: int = Field(ge=1940, le=2025)
    end_year: int = Field(ge=1940, le=2025)

    @model_validator(mode="after")
    def validate_years(self):
        if self.end_year < self.start_year:
            raise ValueError("end_year must be greater than or equal to start_year")
        if self.end_year - self.start_year > 40:
            raise ValueError("Please select no more than 40 years at once")
        return self


class Location(BaseModel):
    id: int | None = None
    name: str
    country: str | None = None
    admin1: str | None = None
    latitude: float
    longitude: float


class CacheStatus(BaseModel):
    raw_weather: Literal["hit", "miss"]
    analysis: Literal["hit", "miss"]
