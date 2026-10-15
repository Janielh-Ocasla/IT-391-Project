import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class History:
    """
    Service history and volunteer hours
    Reads finished work from the assignments table
    """
    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        )

    def is_admin(self, user_id):
        """
        checks whether the user is admin
        Used so admins can look up any volunteer's history

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

    def track_volunteer_hours(self, user_id, volunteer_id=None):
        """
        Volunteers see their own total hours.
        Admin can look up any volunteer's total hours.
        """
        #NOTE: supabase needs to update tasks to add hours to the tasks table, so we can get the hours from there
        pass
    
        """
        try:
            # Check if the user is an admin
            admin = self.is_admin(user_id)

            # Volunteers can only view their own hours
            if not admin:
                volunteer_id = user_id
            elif volunteer_id is None:
                # Admin must look up a specific volunteer, so volunteer_id is required
                print("Please provide a volunteer ID.")
                return None

            # Get completed assignments for this volunteer including the task hours
            result = (
                self.supabase.table("assignments")
                .select("task_id, tasks(hours)")
                .eq("volunteer_id", volunteer_id)
                .eq("status", "completed")
                .execute()
            )

            # Add the hours for each completed task
            total_hours = 0

            for assignment in result.data:
                task = assignment.get("tasks")

                if task:
                    total_hours += float(task.get("hours") or 0)

            return {
                "volunteer_id": volunteer_id,
                "total_hours": round(total_hours, 2)
            }

        except Exception as e:
            print(f"Volunteer hours lookup failed: {e}")
            return None
        """


    def service_history(self, user_id, volunteer_id=None):
        """
        Volunteers see their own completed tasks and cancelled tasks.
        Admin can look up any volunteer by passing volunteer_id,
        or see everyone's history if no volunteer_id is given.

        :param user_id: ID of the user asking
        :param volunteer_id: ID of the volunteer to look up for admin only
        :return: list of assignments with task details, None if something goes wrong
        """
        try:
            # service history includes both completed and cancelled tasks
            query = (
                self.supabase.table("assignments")
                .select("id, task_id, status, assigned_at, cancelled_at, submitted_at, reviewed_at, "
                        "tasks(title, description, deleted_at)")
                .in_("status", ["completed", "cancelled"])
            )
            if self.is_admin(user_id):
                # admin can narrow down to one volunteer
                if volunteer_id:
                    query = query.eq("volunteer_id", volunteer_id)
            else:
                # volunteers can only see their own history
                query = query.eq("volunteer_id", user_id)
            # newest history first
            response = query.order("assigned_at", desc=True).execute()
            return response.data
        except Exception as e:
            print(f"Could not get service history: {e}")
            return None