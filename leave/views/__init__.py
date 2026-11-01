from .add import add, edit  # noqa: F401
from .detail import cancel, view  # noqa: F401
from .list import time_off  # noqa: F401
from .request import mine, request_time_off  # noqa: F401
from .approve import decide, waiting  # noqa: F401
from .statement import adjust, hours_change  # noqa: F401
from .planner import planner  # noqa: F401
from .report import leave_report  # noqa: F401
from .bank_holidays import everyone as bank_holiday_everyone, index as bank_holidays_index  # noqa: F401
from .blackouts import add as blackout_add, delete as blackout_delete, edit as blackout_edit, index as blackouts_index  # noqa: F401
from .settings import leave_settings, type_add, type_edit, types_index  # noqa: F401
from .api import leave_feed  # noqa: F401
from .yearend import decide as year_end_decide, index as year_end  # noqa: F401
from .summary import leave_summary  # noqa: F401
