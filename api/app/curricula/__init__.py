from api.app.curricula.base import CurriculumAdapter
from app.curricula.ib_dp import IBDPAdapter
from app.curricula.ib_cp import IBCPAdapter
# from app.curricula.igcse import IGCSEAdapter
# from app.curricula.btec import BTECAdapter

ADAPTERS = {
    a.code: a() for a in [IBDPAdapter(), IBCPAdapter()]
}

def get_adapter(code: str) -> CurriculumAdapter:
    if code not in ADAPTERS:
        raise ValueError(f"Unsupported curriculum: {code}")
    return ADAPTERS[code]
