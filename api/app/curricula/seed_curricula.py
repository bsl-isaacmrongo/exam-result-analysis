from app.database import SessionLocal
from app.models.curriculum import Curriculum

db = SessionLocal()
for c in [
    Curriculum(code="IB_DP", name="IB Diploma Programme", grade_scale={"min":1,"max":7}),
    Curriculum(code="IB_CP", name="IB Career-related Programme", grade_scale={"min":1,"max":7}),
    Curriculum(code="IGCSE", name="IGCSE", grade_scale={"min":1,"max":9}),
    Curriculum(code="BTEC", name="BTEC", grade_scale={"values":["U","P","M","D","D*"]}),
]:
    db.merge(c)
db.commit()
