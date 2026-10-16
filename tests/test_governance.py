
from person_agents.governance.policy import Permission, PolicyEngine
from person_agents.governance.rate_limiter import RateLimiter


class TestPolicyEngine:
    def test_read_allowed_by_default(self) -> None:
        engine = PolicyEngine()
        assert engine.check(Permission.READ) is True

    def test_shell_denied_by_default(self) -> None:
        engine = PolicyEngine()
        assert engine.check(Permission.SHELL) is False

    def test_grant_revoke(self) -> None:
        engine = PolicyEngine()
        engine.grant(Permission.WRITE)
        assert engine.check(Permission.WRITE) is True
        engine.revoke(Permission.WRITE)
        assert engine.check(Permission.WRITE) is False

    def test_block_rm_rf(self) -> None:
        engine = PolicyEngine()
        ok, _ = engine.check_command("rm -rf /")
        assert ok is False

    def test_block_rm_rf_variant(self) -> None:
        engine = PolicyEngine()
        ok, _ = engine.check_command("rm  -r -f /")
        assert ok is False

    def test_block_git_force(self) -> None:
        engine = PolicyEngine()
        ok, _ = engine.check_command("git push --force origin main")
        assert ok is False

    def test_allow_safe_command(self) -> None:
        engine = PolicyEngine()
        ok, _ = engine.check_command("ls -la /tmp")
        assert ok is True


class TestRateLimiter:
    def test_allow_within_capacity(self) -> None:
        limiter = RateLimiter(llm_capacity=3, llm_refill_rate=0.1)
        assert limiter.allow_llm() is True
        assert limiter.allow_llm() is True
        assert limiter.allow_llm() is True
        assert limiter.allow_llm() is False
