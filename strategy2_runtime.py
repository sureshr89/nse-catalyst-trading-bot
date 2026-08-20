from __future__ import annotations


class Strategy2Runtime:
    """Strategy 2 risk normalization using available paper capital."""
    TARGET_RISK = 1450.0
    MIN_RR = 1.25

    def _normalize_risk(self, signal):
        entry = float(signal["entry"])
        original_stop = float(signal["stop_loss"])
        target = float(signal["target"])
        side = str(signal["signal"]).upper()
        capital = float(getattr(getattr(self, "paper_engine", None), "available_capital", 0.0) or 0.0)
        if entry <= 0 or capital <= 0 or side not in {"BUY", "SELL"}:
            return False
        signal["original_stop_loss"] = original_stop
        current_distance = abs(entry - original_stop)
        if current_distance <= 0:
            return False
        estimated = current_distance / entry * capital
        if estimated < self.TARGET_RISK:
            distance = self.TARGET_RISK / capital * entry
            reward = abs(target - entry)
            rr = reward / distance if distance else 0.0
            if rr < self.MIN_RR:
                return False
            signal["stop_loss"] = entry - distance if side == "BUY" else entry + distance
            signal["risk_adjusted"] = True
            signal["estimated_risk"] = self.TARGET_RISK
            signal["risk_reward"] = rr
            return True
        reward = abs(target - entry)
        rr = reward / current_distance if current_distance else 0.0
        if rr < self.MIN_RR:
            return False
        signal["risk_adjusted"] = False
        signal["estimated_risk"] = estimated
        signal["risk_reward"] = rr
        return True
