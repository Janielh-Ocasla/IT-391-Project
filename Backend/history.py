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

    def track_volunteer_hours(self): #Azul
        """
        Volunteers see their own total hours.
        Admin can look up any volunteer's total hours.
        """
        pass

    def service_history(self): #dariya
        """
        Volunteers see their own completed tasks.
        Admin can look up any volunteer by passing volunteer_id.
        """
        pass