from .views import get_membership, get_pending_count, is_superadmin

def pending_requests(request):
    if not request.user.is_authenticated:
        return {}

    if is_superadmin(request.user):
        return {'pending_request_count': 0}

    membership = get_membership(request.user)
    return {
        'pending_request_count': get_pending_count(membership)
    }