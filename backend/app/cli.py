"""Local bootstrap commands. Run from backend/, or set PYTHONPATH=backend."""

import argparse
import getpass
import os
from datetime import date, timedelta
from pydantic import TypeAdapter, EmailStr
from sqlalchemy import select
from .database import SessionLocal
from .models import (
    Agency,
    Candidate,
    ClientOrg,
    Document,
    Feedback,
    Membership,
    Message,
    Milestone,
    Post,
    Project,
    User,
)
from .security import passwords
from .config import get_settings
from .mail import queue_action


def create_admin():
    email = str(
        TypeAdapter(EmailStr).validate_python(input("Admin email: ").strip())
    ).lower()
    name = input("Admin name: ").strip()
    agency_name = input("Agency name: ").strip()
    password = getpass.getpass("Password (at least 10 characters): ")
    if not name or not agency_name or not 10 <= len(password) <= 128:
        raise SystemExit("Provide names and a password between 10 and 128 characters.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("That email already exists. No changes made.")
        agency = Agency(name=agency_name)
        db.add(agency)
        db.flush()
        user = User(
            name=name,
            email=email,
            role="admin",
            agency_id=agency.id,
            password_hash=passwords.hash(password),
        )
        db.add(user)
        db.flush()
        queue_action(db, email, "verify", {"user_id": user.id}, 1440)
        db.commit()
    print(
        "Agency and administrator created. Check the verification email before signing in."
    )


def seed_demo():
    if get_settings().production:
        raise SystemExit("Demo data is disabled in production.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "admin@example.com")):
            print("Demo data already exists; no changes made.")
            return
        password = os.environ.get("DEMO_PASSWORD", "SearchroomDemo2026!")
        if not 10 <= len(password) <= 128:
            raise SystemExit("DEMO_PASSWORD must have 10–128 characters.")
        hashed = passwords.hash(password)
        agency = Agency(name="Northstar Search", retention_days=180)
        db.add(agency)
        db.flush()
        halcyon = ClientOrg(name="Halcyon Labs", agency_id=agency.id)
        meridian = ClientOrg(name="Meridian Finance", agency_id=agency.id)
        db.add_all([halcyon, meridian])
        db.flush()
        admin = User(
            name="Alex Morgan",
            email="admin@example.com",
            role="admin",
            agency_id=agency.id,
            password_hash=hashed,
            email_verified=True,
        )
        recruiter = User(
            name="Jamie Parker",
            email="recruiter@example.com",
            role="recruiter",
            agency_id=agency.id,
            password_hash=hashed,
            email_verified=True,
        )
        client = User(
            name="Sam Taylor",
            email="client@example.com",
            role="client",
            agency_id=agency.id,
            client_org_id=halcyon.id,
            password_hash=hashed,
            email_verified=True,
        )
        db.add_all([admin, recruiter, client])
        db.flush()
        start = date.today() - timedelta(days=14)
        product = Project(
            agency_id=agency.id,
            client_org_id=halcyon.id,
            title="Head of Product",
            description="Find a thoughtful product leader to shape the next chapter at Halcyon Labs. The team is growing its B2B platform and needs someone who can turn customer insight into a clear product direction.",
            ideal_profile="Experience leading a product team in a growing software business. A hands-on approach, strong commercial judgement and a track record of building products customers love.",
            agreement_terms="Retained search engagement. Fee: 25% of agreed first-year base salary, paid in three equal instalments at launch, shortlist delivery and successful appointment. Weekly progress updates. Terms shown here are fictional demo content.",
            start_date=start,
            end_date=start + timedelta(days=60),
        )
        tech = Project(
            agency_id=agency.id,
            client_org_id=meridian.id,
            title="Chief Technology Officer",
            description="Partner with Meridian Finance to appoint a technology leader for its next phase of growth. A search focused on platform scale, engineering culture and pragmatic delivery.",
            ideal_profile="Senior engineering leadership in financial services or a regulated technology business.",
            agreement_terms="Retained search. Commercial terms to be agreed with the client.",
            start_date=start + timedelta(days=7),
            end_date=start + timedelta(days=80),
        )
        db.add_all([product, tech])
        db.flush()
        db.add_all(
            [
                Membership(project_id=product.id, user_id=recruiter.id),
                Membership(project_id=product.id, user_id=client.id),
                Membership(project_id=tech.id, user_id=recruiter.id),
            ]
        )
        candidates = [
            Candidate(
                project_id=product.id,
                name="Olivia Bennett",
                current_role="Group Product Manager",
                company="Arc Software",
                summary="Led two product teams through a successful move into enterprise customers. Strong customer research experience and a calm, collaborative leadership style.",
                stage="Interviewing",
                client_visible=True,
            ),
            Candidate(
                project_id=product.id,
                name="Daniel Chen",
                current_role="Head of Product",
                company="Form & Function",
                summary="Built a product function from four to fifteen people. Particularly strong in product strategy and commercial prioritisation.",
                stage="Shortlisted",
                client_visible=True,
            ),
            Candidate(
                project_id=product.id,
                name="Amara Okafor",
                current_role="Product Director",
                company="Clearpath",
                summary="Experienced B2B product leader with a track record of simplifying complex workflows and improving customer retention.",
                stage="Shortlisted",
                client_visible=True,
            ),
            Candidate(
                project_id=product.id,
                name="Thomas Reed",
                current_role="Senior Product Manager",
                company="Bluepeak",
                summary="Initial conversation planned. Agency review in progress.",
                stage="Identified",
                client_visible=False,
            ),
        ]
        db.add_all(candidates)
        db.flush()
        db.add(
            Feedback(
                candidate_id=candidates[0].id,
                author_id=client.id,
                body="The enterprise experience looks particularly relevant. Looking forward to the first conversation.",
            )
        )
        db.add(
            Document(
                project_id=product.id,
                title="Example document reference",
                url="https://example.com",
            )
        )
        db.add(
            Post(
                project_id=product.id,
                author_id=recruiter.id,
                body="The initial shortlist is ready to review. We focused on leaders who have scaled a product team while staying close to customers. Three profiles are now shared in the Candidates tab.",
            )
        )
        db.add(
            Post(
                project_id=product.id,
                author_id=client.id,
                body="A note from our leadership team: experience working with a founder-led business would be a real advantage. Happy to explore this in the first interviews.",
            )
        )
        db.add_all(
            [
                Message(
                    project_id=product.id,
                    author_id=recruiter.id,
                    body="Hi Sam, welcome to the search workspace. I’ll keep the shortlist and timeline up to date here.",
                ),
                Message(
                    project_id=product.id,
                    author_id=client.id,
                    body="Thanks Jamie. It’s helpful to have everything in one place. I’ve added a note on the update board.",
                ),
                Message(
                    project_id=product.id,
                    author_id=recruiter.id,
                    body="Great, thanks. Olivia is ready for a first interview — let me know which days work for your team.",
                ),
            ]
        )
        db.add_all(
            [
                Milestone(
                    project_id=product.id,
                    title="Search briefing & role alignment",
                    description="Agree the role, candidate profile and search approach.",
                    target_date=start,
                    completed=True,
                ),
                Milestone(
                    project_id=product.id,
                    title="Share the initial shortlist",
                    description="Present three candidates for client review.",
                    target_date=date.today() - timedelta(days=2),
                    completed=True,
                ),
                Milestone(
                    project_id=product.id,
                    title="Confirm interview availability",
                    description="Agree interview slots with the client team.",
                    target_date=date.today() - timedelta(days=1),
                ),
                Milestone(
                    project_id=product.id,
                    title="Complete first-round interviews",
                    description="Interview all shortlisted candidates and gather feedback.",
                    target_date=date.today() + timedelta(days=10),
                ),
                Milestone(
                    project_id=product.id,
                    title="Final selection & offer",
                    description="Choose the preferred candidate and agree an offer.",
                    target_date=date.today() + timedelta(days=30),
                ),
            ]
        )
        db.commit()
    print(
        "Fictional demo data created: admin@example.com, recruiter@example.com, client@example.com."
    )
    print("Use DEMO_PASSWORD, or the documented default if you did not set it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Searchroom local setup")
    parser.add_argument("command", choices=["create-admin", "seed-demo"])
    args = parser.parse_args()
    create_admin() if args.command == "create-admin" else seed_demo()
