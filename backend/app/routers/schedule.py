from fastapi import APIRouter
from app.schemas.schedule import PrecheckRequest, ScheduleRequest
from app.services.mortgage_service import MortgageService
router = APIRouter()


@router.post("/schedule/precheck")
def post_schedule_precheck(body: PrecheckRequest):
    with MortgageService() as s:
        return s.precheck(body.principal, body.annual_rate, body.months,
                          body.loan_id, body.preview_rows)


@router.post("/schedule")
def post_schedule(body: ScheduleRequest):
    with MortgageService() as s:
        out = s.schedule(body.principal, body.annual_rate, body.months,
                          body.loan_id, body.persist, body.preview_rows,
                          body.receipt_code)
        return out
