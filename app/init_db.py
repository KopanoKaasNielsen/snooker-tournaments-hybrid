# idempotent seed
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models

def seed_data():
    db: Session = SessionLocal()
    # add players if missing
    names = ["Ronnie O'Sullivan","Mark Selby","Judd Trump","Neil Robertson","John Higgins","Ding Junhui","Shaun Murphy","Kyren Wilson"]
    for n in names:
        if not db.query(models.Player).filter_by(name=n).first():
            db.add(models.Player(name=n))
    # add a sample tournament
    if not db.query(models.Tournament).filter_by(name='Botswana Open').first():
        db.add(models.Tournament(name='Botswana Open'))
    db.commit()
    db.close()
    print('✅ Database seeded with players and tournament.')

if __name__ == '__main__':
    seed_data()

# NOTE: avoid duplicates by checking existence before inserting
