from functools import wraps
from django.shortcuts import redirect

def require_role(required_role):
    from .views import get_membership, has_role, is_superadmin
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if is_superadmin(request.user):
                return view_func(request, *args, **kwargs)
            membership = get_membership(request.user)
            if not membership or not has_role(membership, required_role):
                return redirect('project_list')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
