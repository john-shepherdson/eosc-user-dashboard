from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, Response
from starlette import status

from starlette.responses import RedirectResponse, JSONResponse
from fastapi import HTTPException

from app.core.config import OIDC_ISSUER
from app.schemas.LogoutResponse import LogoutResponse
from app.schemas.SessionData import SessionData
from app.schemas.UserInfoResponse import UserInfoResponse
from app.services.rp_handler_service import RpHandlerService

from app.utils.cookie_validators import backend, cookie, verifier

router = APIRouter()


@router.get("/request")
async def request(rph_service=Depends(RpHandlerService)):
    try:
        result = rph_service.handler.begin(issuer_id=OIDC_ISSUER)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f'Something went wrong: {err} {repr(err)}')
    else:
        return RedirectResponse(status_code=303, url=result['url'])


@router.get("/checkin")
async def checkin(code: str, state: str, rph_service=Depends(RpHandlerService)):
    if not state:
        return RedirectResponse(status_code=400, url="http://localhost:4200")

    try:
        aai_response = rph_service.handler.finalize(OIDC_ISSUER, dict(code=code, state=state))

        session_id = uuid4()
        username = aai_response["userinfo"]["name"]
        session_data = SessionData(username=username, aai_state=state)
        await backend.create(session_id, session_data)
        auth_response = RedirectResponse(status_code=303, url="http://localhost:4200")
        cookie.attach_to_response(auth_response, session_id)
        return auth_response
    except Exception:
        return RedirectResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            url="http://localhost:4200",
            headers={"WWW-Authenticate": "Bearer"}
        )


@router.get("/userinfo", dependencies=[Depends(cookie)], response_model=UserInfoResponse)
async def user_info(session_data: SessionData = Depends(verifier)) -> UserInfoResponse:
    return UserInfoResponse(username=session_data.username)


@router.post("/logout")
async def logout(response: Response, session_id: UUID = Depends(cookie)):
    await backend.delete(session_id)
    cookie.delete_from_response(response)
    return LogoutResponse(msg="Session have been removed")
