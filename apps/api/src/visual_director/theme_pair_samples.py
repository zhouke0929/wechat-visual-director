"""Illustrative pairs that distinguish a change from two coexisting options."""

TIMELINE = (
    "改版前，入口、报到时间和交通说明写在同一段里。",
    "改版后，入口和报到时间移到开头，交通说明单独列出。",
)
COMPARISON = (
    "现场签到：到服务台报姓名，由工作人员核对名单。",
    "提前登记：出示确认码，由工作人员核对登记信息。",
)

_TIMELINE_DETAIL = (
    "来自不同方向的人需要在同一段里找适用的路线；想确认签到台位置，也要先略过交通说明，才知道进门后去哪里。",
    "从主入口进来的人可以先找到签到台；从其他方向来的参与者还可以往下看，找到对应的路线。",
)
_COMPARISON_DETAIL = (
    "不需要提前填写表单；如果报名姓名和现场使用的名字不同，可以请工作人员协助查询。",
    "出发前填写联络信息，确认后可把确认码存到手机。到场时工作人员只核对登记信息；如临时换了同行人，请在服务台更新名单。",
)


def review_pair(role: str, *, long: bool = False) -> tuple[str, str]:
    sample, details = (TIMELINE, _TIMELINE_DETAIL) if role == "before_after_timeline" else (COMPARISON, _COMPARISON_DETAIL)
    return (sample[0] + details[0], sample[1] + details[1]) if long else sample
