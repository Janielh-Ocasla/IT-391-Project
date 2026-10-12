import os
from datetime import datetime, timezone
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
            
    def create_announcement(self, user_id, title, content): 
        """
        posts a new announcement and can only be posted by admin.

        :param user_id: ID of the admin posting the announcement
        :param title: title of the announcement
        :param content: the information of the announcement
        :return: True if announcement posted, False otherwise
        """
        try:
            if not self.is_admin(user_id):
                print("Only admins can post announcements.")
                return False
            # check and clean the required information
            title = title.strip()
            content = content.strip()
            if not title or not content:
                print("Announcement failed: Title and content are required!")
                return False
            # insert new announcement into the database
            self.supabase.table("announcements").insert({
                "title": title,
                "content": content,
                "created_by": user_id
            }).execute()
            print("Announcement posted successfully.")
            return True
        except Exception as e:
            print(f"An error occurred while posting the announcement: {e}")
            return False

    def edit_announcement(self, user_id, announcement_id, title=None, content=None):
        """
        updates announcement and can only be edited by admin.

        :param user_id: ID of the admin editing the announcement
        :param announcement_id: ID of the announcement to edit
        :param title: new title
        :param content: new content
        :return: True if announcement updated, False otherwise
        """
        try:
            if not self.is_admin(user_id):
                print("Only admins can edit announcements.")
                return False
            # store fields that need to be updated
            updates = {}
            if title is not None:
                title = title.strip()
                if not title:
                    print("Announcement update failed: Title cannot be empty!")
                    return False
                updates["title"] = title
            if content is not None:
                content = content.strip()
                if not content:
                    print("Announcement update failed: Content cannot be empty!")
                    return False
                updates["content"] = content
            if not updates:
                print("Nothing to update!")
                return False
            # record the time of the latest update
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            # find announcement and apply the updates
            response = (
                self.supabase.table("announcements")
                .update(updates)
                .eq("announcement_id", announcement_id)
                .execute()
            )
            # check whether the announcement was found and updated
            if not response.data:
                print("Announcement not found or you do not have permission to edit it.")
                return False
            print("Announcement updated successfully.")
            return True
        except Exception as e:
            print(f"An error occurred while editing the announcement: {e}")
            return False

    def delete_announcement(self, user_id, announcement_id):
        """
        deletes announcement and by admin only.

        :param user_id: ID of the admin deleting the announcement
        :param announcement_id: ID of the announcement to delete
        :return: True if announcement deleted, False otherwise
        """
        try:
            if not self.is_admin(user_id):
                print("Only admins can delete announcements.")
                return False
            # find and delete the announcement from database
            response = (
                self.supabase.table("announcements")
                .delete()
                .eq("announcement_id", announcement_id)
                .execute()
            )
            # check whether the announcement was found and deleted
            if not response.data:
                print("Announcement not found or you do not have permission to delete it.")
                return False
            print("Announcement deleted successfully.")
            return True
        except Exception as e:
            print(f"An error occurred while deleting the announcement: {e}")
            return False

    def list_announcements(self): 
        """
        returns all announcements with the newest first and 
        can be viewed by both admin and volunteer.

        :return: List of announcements, None if something goes wrong
        """
        try:
            response = (
                self.supabase.table("announcements")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return response.data
        except Exception as e:
            print(f"Could not list announcements: {e}")
            return None