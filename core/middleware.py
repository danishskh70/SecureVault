class LastPageMiddleware:
    """Stores last visited page in session, skipping some URLs like login, logout."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method == 'GET' and request.path not in ['/logout/', '/login/', '/projects/']:
            # Save current path as previous page for next request
            request.session['previous_page'] = request.path
        return response