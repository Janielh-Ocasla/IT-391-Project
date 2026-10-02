import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Task:
    """
    Managing and viewing tasks
    """

    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        )

    def is_admin(self, user_id):
        """
        check whether the user is admin
        Used to restrict admin-only actions like create, edit & delete
        """
        try:
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

    def create_task(self): #dariya
        pass

    def edit_task(self): #dariya
        pass

    def delete_task(self): #dariya
        pass

    def task_info(self): #dariya
        pass

    def list_task(self): #azul
        """
        Volunteers see only available tasks, while admin see all tasks.
        """
        pass