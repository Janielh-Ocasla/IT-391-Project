import os
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Assignment:
    """
    Volunteer taking and finishing a task
    """

    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        )

    def is_admin(self, user_id):
        """
        checks whether the user is admin
        Used to restrict admin-only actions like verify photo

        :param user_id: ID of the user to check
        :return: True if user is an admin, False otherwise
        """
        try:
            # get the user's role from profiles
            profile = (
                self.supabase.table("profiles")
                .select("role")
                .eq("id", user_id)
                .single()
                .execute()
            )
            return profile.data["role"] == "admin"
        except Exception as e:
            print(f"Role check failed: {e}")
            return False

    def pick_task(self, user_id, task_id): 
        """
        Assigns a task to a volunteer.
        Creates an assignment row and marks the task as in_progress.
        """
        try:
            # make sure the task is still open before picking it
            task = (
                self.supabase.table("tasks")
                .select("status")
                .eq("id", task_id)
                .single()
                .execute()
            )
            if task.data["status"] != "open":
                print("Pick failed: this task is no longer available.")
                return None
            assignment = (
                self.supabase.table("assignments")
                .insert({
                    "task_id": task_id,
                    "volunteer_id": user_id,
                    "status": "assigned"
                })
                .execute()
            )
            self.supabase.table("tasks") \
                .update({"status": "in_progress"}) \
                .eq("id", task_id) \
                .execute()

            return assignment.data

        except Exception as e:
            print(f"Task assignment failed: {e}")
            return None

    def cancel_task(self, user_id, task_id): 
        """
        Cancels a volunteer's assignment.
        Updates assignment status and resets task status.
        """
        try:
            assignment = (
                self.supabase.table("assignments")
                .select("*")
                .eq("task_id", task_id)
                .eq("volunteer_id", user_id)
                .eq("status", "assigned")
                .execute()
            )

            if not assignment.data:
                print("Cancel failed: no assignment found for this user.")
                return None

            assignment_id = assignment.data[0]["id"]

            self.supabase.table("assignments") \
                .update({
                    "status": "cancelled",
                    "cancelled_at": datetime.now(timezone.utc).isoformat()
                }) \
                .eq("id", assignment_id) \
                .execute()

            self.supabase.table("tasks") \
                .update({"status": "open"}) \
                .eq("id", task_id) \
                .execute()

            return {"message": "Task cancelled"}

        except Exception as e:
            print(f"Task cancel failed: {e}")
            return None

    def upload_photo(self): #Azul
        """
        Volunteer uploads the delivery photo as proof.
        Photo can be retaken until submitted
        """
        pass  

    def submit_task(self): #Azul
        """
        Volunteer presses submit to say the delivery is done.
        Only works if a photo was uploaded first.
        """
        pass 

    def verify_delivery(self): #Azul
        """
        Admin will check the photo and verify whether the task was complete or not
        """
        pass

    def track_task_status(self): #Azul
        """
        Volunteer can see their own status, while admin can see everyone's.
        """
        pass