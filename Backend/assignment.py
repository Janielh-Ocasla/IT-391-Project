import os
import mimetypes
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

    def upload_photo(self, user_id, task_id, file_path):
        """
        Volunteer uploads the delivery photo as proof.
        Photo can be retaken until submitted
        """
        #NOTE: only one photo is allowed per assignment, so if the volunteer uploads a new photo, it will overwrite the previous one
        
        try:
        # Find the volunteer's active assignment
            assignment = (
                self.supabase.table("assignments")
                .select("id, status")
                .eq("task_id", task_id)
                .eq("volunteer_id", user_id)
                .eq("status", "assigned")
                .single()
                .execute()
            )

            assignment_id = assignment.data["id"]

            # Get the photo's file name and type
            file_name = os.path.basename(file_path)
            content_type = (
                mimetypes.guess_type(file_name)[0]
                or "application/octet-stream"
            )

            # Create a unique path for the photo to not overwrite previous uploads
            timestamp = datetime.now(timezone.utc).strftime(
                "%Y%m%d%H%M%S%f"
            )
            
            #store the photo in a folder named after the user and assignment, with a timestamp to avoid overwriting
            photo_path = (
                f"{user_id}/{assignment_id}/"
                f"{timestamp}_{file_name}"
            )

            # Upload the photo to Supabase Storage
            with open(file_path, "rb") as photo:
                self.supabase.storage.from_("task-photo").upload(
                    path=photo_path,
                    file=photo,
                    file_options={"content-type": content_type}
                )

            # Save the photo path in the assignment
            self.supabase.table("assignments").update({
                "photo_path": photo_path
            }).eq("id", assignment_id).execute()

            return photo_path

        except Exception as e:
            print(f"Photo upload failed: {e}")
            return None

    def submit_task(self, user_id, task_id):
        """
        Volunteer presses submit to say the delivery is done.
        Only works if a photo was uploaded first.
        """
        try:
            # Find the volunteer's active assignment
            assignment = (
                self.supabase.table("assignments")
                .select("id, photo_path")
                .eq("task_id", task_id)
                .eq("volunteer_id", user_id)
                .eq("status", "assigned")
                .single()
                .execute()
            )

            # Check that a photo was uploaded
            if not assignment.data["photo_path"]:
                print("Submit failed: upload a photo first.")
                return None

            # Update the assignment status to submitted and record the submission time
            result = (
                self.supabase.table("assignments")
                .update({
                    "status": "submitted",
                    "submitted_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                })
                .eq("id", assignment.data["id"])
                .execute()
            )
            # Return the updated assignment data
            return result.data

        except Exception as e:
            print(f"Task submission failed: {e}")
            return None
 

    def verify_delivery(self, admin_id, assignment_id, approved):
        """
        Admin will check the photo and verify whether the task was complete or not
        """
        # NOTE: set status to "completed", since service_history method filters on this word
        try:
            # Check if the user is an admin for verification
            if not self.is_admin(admin_id):
                print("Verification failed: admin access required.")
                return None

            # Check if the assignment is in submitted status
            assignment = (
                #find the assignment using its ID and get the details
                self.supabase.table("assignments")
                .select("id, task_id, status")
                .eq("id", assignment_id)
                .eq("status", "submitted")
                .single()
                .execute()
            )

            task_id = assignment.data["task_id"]

            if approved:
                # Admin marks the task as completed
                new_status = "completed"
            else:
                # Rejected tasks are sent back to assigned for volunteer to resubmit
                new_status = "assigned"
            
            # update the status, who reviewed it, and the review timestamp
            result = (
                self.supabase.table("assignments")
                .update({
                    "status": new_status,
                    "reviewed_by": admin_id,
                    "reviewed_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "submitted_at": None if not approved else
                        datetime.now(timezone.utc).isoformat()
                })
                .eq("id", assignment_id)
                .execute()
            )

            # Mark the task completed only when approved
            if approved:
                self.supabase.table("tasks").update({
                    "status": "completed"
                }).eq("id", task_id).execute()

            return result.data

        except Exception as e:
            print(f"Delivery verification failed: {e}")
            return None

    def track_task_status(self, user_id):
        """
        Volunteer can see their own status, while admin can see everyone's.
        """
        try:
            # check if the user is an admin
            admin = self.is_admin(user_id)

            query = (
                #see all assignments with task details (title and status)
                self.supabase.table("assignments")
                .select("*, tasks(title, status)")
            )

            # volunteers can only see their own assignments
            if not admin:
                query = query.eq("volunteer_id", user_id)

            result = query.execute()
            return result.data

        except Exception as e:
            print(f"Task status lookup failed: {e}")
            return None
