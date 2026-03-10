class AuthContext:
    """더미 인증 컨텍스트. is_authenticated=False → 모든 도구가 더미 데이터 반환."""
    def __init__(self):
        self.stat = None
        self.user_id = None
        self.emp_code = None
        self.dept_id = None
        self.k = None
        self.user_nm = "데모 사용자"
        self.docdept_nm = "AI 솔루션팀"
        self.docdept_id = None

    @classmethod
    def demo(cls):
        return cls()

    @property
    def is_authenticated(self):
        return False
