from django.db import migrations
from django.utils.text import slugify

DEPARTMENTS = [
    ("General Medicine", "🩺", "Primary care for common illnesses, routine check-ups and referrals to specialists."),
    ("Internal Medicine", "🩺", "Diagnosis and long-term management of adult conditions such as diabetes and hypertension."),
    ("Gynaecology", "🤰", "Women's health, antenatal care, family planning and gynaecological concerns."),
    ("Children Health Care Centre", "🧒", "Paediatric care from newborns to adolescents, immunisation and growth monitoring."),
    ("Eye Care Centre", "👁️", "Vision tests, eye examinations, glasses prescriptions and treatment of eye conditions."),
    ("Dentition and Oral Health Care", "🦷", "Dental check-ups, cleaning, fillings, extractions and oral health education."),
    ("Cardiology", "🫀", "Heart health, blood pressure management, ECG review and cardiac follow-up."),
    ("Neurology", "🧠", "Headaches, seizures, memory concerns, nerve problems and neurological assessment."),
    ("ENT (Ear, Nose & Throat)", "👂", "Ear infections, hearing concerns, sinus problems, sore throats and voice disorders."),
    ("Orthopaedics & Bone Health", "🦴", "Joint and bone pain, fractures, osteoporosis screening and sports injuries."),
]


def seed(apps, schema_editor):
    Department = apps.get_model("clinic", "Department")
    for title, icon, description in DEPARTMENTS:
        if not Department.objects.filter(title=title).exists():
            Department.objects.create(
                title=title, slug=slugify(title)[:200], icon=icon, description=description, is_active=True
            )


def unseed(apps, schema_editor):
    Department = apps.get_model("clinic", "Department")
    Department.objects.filter(title__in=[d[0] for d in DEPARTMENTS], doctors__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("clinic", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
