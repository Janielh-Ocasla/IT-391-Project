import os
from datetime import datetime, timezone
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

    def create_task(self, user_id, title, description=None):
        """
        Creates a new task with status 'open' and can only be created by Admin.

        :param user_id: ID of the admin creating the task
        :param title: Title of the task
        :param description: description of the task
        :return: True if task created, False otherwise
        """
        try:
            if not self.is_admin(user_id):
                print("Only admins can create tasks.")
                return False
            # check and clean the required information
            title = title.strip()
            if not title:
                print("Task creation failed: Title is required!")
                return False
            # store task details 
            task_data = {
                "title": title,
                "description": (description or "").strip() or None,
                "status": "open",
                "created_by": user_id
            }
            # insert new task into the database
            self.supabase.table("tasks").insert(task_data).execute()
            print("Task created successfully.")
            return True
        except Exception as e:
            print(f"An error occurred during task creation: {e}")
            return False

    def edit_task(self, user_id, task_id, title=None, description=None):
        """
        Updates the fields that are provided and can only be edited by admin.

        :param user_id: ID of the admin editing the task
        :param task_id: ID of the task to edit
        :param title: new title for the task
        :param description: new description for the task
        :return: True if task updated, False otherwise
        """ 
        try:
            if not self.is_admin(user_id):
                print("Only admins can edit tasks.")
                return False
            # store fields that need to be updated
            updates = {}
            if title is not None:
                title = title.strip()
                if not title:
                    print("Task update failed: Title cannot be empty!")
                    return False
                updates["title"] = title
            if description is not None:
                updates["description"] = description.strip() or None
            if not updates:
                print("Nothing to update.")
                return False
            # record the time of the latest update
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            # find task and apply the updates
            response = (
                self.supabase.table("tasks")
                .update(updates)
                .eq("id", task_id)
                .execute()
            )
            # check if the task was found and updated
            if not response.data:
                print("Task not found or you do not have permission to edit it.")
                return False
            print("Task updated successfully.")
            return True
        except Exception as e:
            print(f"An error occurred while editing the task: {e}")
            return False

    def delete_task(self, user_id, task_id):
        """
        Delete a task and can only be deleted by admin.

        :param user_id: ID of the admin deleting the task
        :param task_id: ID of the task to delete
        :return: True if task deleted, False otherwise
        """ 
        try:
            if not self.is_admin(user_id):
                print("Only admins can delete tasks.")
                return False
            # find and delete the task from database
            response = (
                self.supabase.table("tasks")
                .delete()
                .eq("id", task_id)
                .execute()
            )
            # check if the task was found and deleted
            if not response.data:
                print("Task not found or you do not have permission to delete it.")
                return False
            print("Task deleted successfully.")
            return True
        except Exception as e:
            print(f"An error occurred while deleting the task: {e}")
            return False

    def task_info(self, task_id): 
        """
        shows the details of a task or return None if not found
        can be checked by both admin and volunteer

        :param task_id: ID of the task to view
        :return: Task information if found, None otherwise
        """
        try:
            # find the task using its ID and get the details
            response = (
                self.supabase.table("tasks")
                .select("*")
                .eq("id", task_id)
                .single()
                .execute()
            )
            # return task information
            return response.data
        except Exception as e:
            print(f"Could not get task information: {e}")
            return None

    def list_task(self, user_id): 
        """
        Volunteers see only available tasks, while admin see all tasks.
        """
        try:
            if self.is_admin(user_id):
                response = (
                    self.supabase.table("tasks")
                    .select("*")
                    .order("created_at", desc=True)
                    .execute()
                )
                return response.data
            
            response = (
                self.supabase.table("tasks")
                .select("*")
                .eq("status", "open")
                .order("created_at", desc=True)
                .execute()
            )
            return response.data

        except Exception as e:
            print(f"Could not list tasks: {e}")
            return None