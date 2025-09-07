from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

class ArtworkType(IntEnum):
    ILLUST = 0
    MANGA = 1
    UGOIRA = 2
    
    def __str__(self):
        return {
            self.ILLUST: "插画",
            self.MANGA: "漫画",
            self.UGOIRA: "动图"
        }.get(self, "未知")
    
class ArtworkRestrict(IntEnum):
    NORMAL = 0
    R18 = 1
    R18G = 2
    
    def __str__(self):
        return {
            self.NORMAL: "普通",
            self.R18: "R18",
            self.R18G: "R18G"
        }.get(self, "未知")

@dataclass
class Tag:
    tag: str
    translation: str
    display_tag: str = ""
    
    def __post_init__(self):
        self.display_tag = f"{self.tag}({self.translation})" if self.tag != self.translation else self.tag

@dataclass
class Artwork:
    id: int
    title: str = None
    comment: str = None
    pageCount: int = None
    user_id: int = None
    user_name: str = None
    type: ArtworkType = ArtworkType.ILLUST
    restrict: ArtworkRestrict = ArtworkRestrict.NORMAL
    aiType: int = None
    timestamp: datetime = None
    width: int = None
    height: int = None
    tags: list[Tag] = field(default_factory=list)
    ugoiraInfo: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)
    is_deleted: bool = False
    
    def __post_init__(self):
        if self.tags and not isinstance(self.tags[0], Tag):
            self.tags = [Tag(**tag) for tag in self.tags]
        if not isinstance(self.type, ArtworkType):
            self.type = ArtworkType(self.type)
        if not isinstance(self.restrict, ArtworkRestrict):
            self.restrict = ArtworkRestrict(self.restrict)
            
    def __str__(self):
        return "\n".join([str(k) + ": " + str(v) for k, v in self.__dict__.items() if not k.startswith('_')]) + "\n" + "-" * 40
            
            
@dataclass
class Image:
    id: str
    idNum: int
    index: int
    url: str
    width: int
    height: int
    ext: str
    original_path: str = ""
    compressed_path: str = ""
    is_deleted: bool = False