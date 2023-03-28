import pydantic
import typing as tp


def to_camel(snake_str: str) -> str:
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class SteamTokenResponse(pydantic.BaseModel):
    token: str | None
    refresh_token: str | None
    callback: tp.Optional[tp.Callable]


class MimbusBaseResponse(pydantic.BaseModel):
    state: str


class AccountInfo(pydantic.BaseModel):
    uid: int
    google_account: str | None
    apple_account: str | None
    steam_account: str


class UserAuth(pydantic.BaseModel):
    uid: int
    public_id: int
    db_id: int
    auth_code: str
    last_login_date: str
    last_update_date: str
    data_version: int


class SteamLoginData(pydantic.BaseModel):
    user_auth: UserAuth
    account_info: AccountInfo

    class Config:
        alias_generator = to_camel


class SteamLoginResponse(MimbusBaseResponse):
    result: SteamLoginData


class UserInfo(pydantic.BaseModel):
    uid: int
    level: int
    exp: int
    stamina: int
    last_stamina_recover: str
    current_storybattle_nodeid: int


class MailList(pydantic.BaseModel):
    mail_id: int
    sent_date: str
    expiry_date: str
    content_id: int
    attachments: list
    parameters: list


class Update(pydantic.BaseModel):
    user_info: UserInfo
    mail_list: list[MailList]

    class Config:
        alias_generator = to_camel


class Profile(pydantic.BaseModel):
    public_uid: str
    illust_id: int
    illust_gacksung_level: int
    sentence_id: int
    word_id: int
    banner_ids: list[int]
    level: int
    date: str


class LoadAllResults(pydantic.BaseModel):
    profile: Profile


class LoadAllResponse(MimbusBaseResponse):
    updated: Update
    result: LoadAllResults
