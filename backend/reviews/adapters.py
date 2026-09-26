from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """No local username/password accounts. Google is the only way in."""

    def is_open_for_signup(self, request):
        return False


class GoogleSignupAdapter(DefaultSocialAccountAdapter):
    """Social signup would otherwise inherit the closed account adapter."""

    def is_open_for_signup(self, request, sociallogin):
        return True
