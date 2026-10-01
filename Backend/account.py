import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Account:
    """
    Handles account creation, login, logout, reset password using Supabase 
    """

    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        )

    def create_account(self, email, password, first_name, last_name, phone):
        """
        Creates a new account
        Returns True if successful, False otherwise
        """
        try:
            # clean and normalize user inputs
            email = email.strip().lower()
            first_name = first_name.strip()
            last_name = last_name.strip()
            phone = phone.strip()

            # check required information
            if not email or not password or not first_name or not last_name:
                print("Account creation failed: Required information is missing")
                return False
            
            # create the account in Supabase
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            if response.user is None:
                print("Account creation failed.")
                return False

            # store user information in the profiles
            profile_data = {
                "id": response.user.id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "role": "volunteer"
            }
            self.supabase.table("profiles").insert(profile_data).execute()
            print("Account created successfully.")
            return True
        
        except Exception as e:
            print(f"An error occurred during account creation: {e}")
            return False
        
    def login(self, email, password):
        """
        Logs a user in and returns their role so the application knows which dashboard to show
        """
        try:
            # clean and normalize email
            email = email.strip().lower()
            # check login information with Supabase
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if response.user is None:
                print("Login failed: Invalid email or password")
                return False, None

            # get the user's role from the profiles table
            profile = (
                self.supabase.table("profiles")
                .select("role")
                .eq("id", response.user.id)
                .single()
                .execute()
            )
            role = profile.data["role"]
            print(f"Login successful. Role:{role}")
            return True, role
        
        except Exception as e:
            print(f"Login failed: {e}")
            return False, None

    def logout(self):
        """
        Logs out the current user.
        """
        try:
            # end the current session
            self.supabase.auth.sign_out()
            print("Logged out successfully.")
            return True
        except Exception as e:
            print(f"Error during logout: {e}")
            return False

    def reset_password(self):
        pass

    def authenticate_user(self):
        pass

    def update_profile(self):
        pass