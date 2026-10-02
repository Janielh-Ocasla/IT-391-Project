import os
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

    def pick_task(self): #Azul
        pass

    def cancel_task(self): #Azul
        pass
