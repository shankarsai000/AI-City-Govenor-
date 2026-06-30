"""
Conflict resolution strategies based on priorities and severity levels.

Priorities:
- Critical conflicts reject/block the mutation.
- High conflicts escalate the request to human/manual approval.
- Low conflicts are auto-resolved (proceed).
"""
from app.city_state.domains import StateMutation, Conflict, Resolution

class ConflictResolver:
    """Orchestrates resolution policies for detected physical/resource conflicts."""

    @staticmethod
    async def resolve(conflicts: list[Conflict], mutation: StateMutation) -> Resolution:
        """
        Evaluate conflicts against the mutation priority matrix.
        Returns a Resolution model with recommended action.
        """
        if not conflicts:
            return Resolution(action="proceed", reason="No conflicts detected.")

        # Determine highest severity conflict
        highest_severity = "low"
        severities = ["low", "medium", "high", "critical"]
        
        for c in conflicts:
            if severities.index(c.severity) > severities.index(highest_severity):
                highest_severity = c.severity

        # Priority resolution matrix
        if highest_severity == "critical":
            return Resolution(
                action="block",
                reason=f"Blocked due to critical conflicts: {[c.description for c in conflicts if c.severity == 'critical']}",
                resolved_conflicts=conflicts
            )
            
        elif highest_severity == "high":
            return Resolution(
                action="escalate",
                reason="Escalated to human operator for manual review (high severity conflicts).",
                resolved_conflicts=conflicts
            )
            
        elif highest_severity == "medium":
            # Defer / queue mutation or escalate
            return Resolution(
                action="escalate",
                reason="Escalated due to unresolved medium physical constraints.",
                resolved_conflicts=conflicts
            )
            
        else: # Low severity
            return Resolution(
                action="proceed",
                reason="Proceeding with auto-resolved low severity warnings.",
                resolved_conflicts=conflicts
            )
