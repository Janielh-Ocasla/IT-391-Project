import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Announcement:
    """
    Managing and viewing announcements
    """
    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        )

    def is_admin(self, user_id):
            """
            checks whether the user is admin
            Used to restrict admin-only actions like create, edit & delete
    
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
            
    def create_announcement(self): #dariya
        """
        posts a new announcement and can only be posted by admin.
        """
        pass

    def edit_announcement(self): #dariya
        """
        updates announcement and can only be edited by admin.
        """
        pass

    def delete_announcement(self): #dariya
        """
        deletes announcement and by admin only.
        """
        pass

    def list_announcements(self): #dariya
        """
        returns all announcements with the newest first and 
        can be viewed by both admin and volunteer.
        """
        pass