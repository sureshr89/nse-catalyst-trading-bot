from __future__ import annotations


class Strategy2Runtime:
    """Small risk-normalization runtime used by Strategy 2 and its tests."""
    TARGET_RISK = 1450.0
    MIN_RR = 1.25

    def _normalize_risk(self, signal):
        entry = float(signal["entry"])
        stop = float(signal["stop_loss"])
        target = float(signal["target"])
        side = str(signal["signal"]).upper()
        signal["original_stop_loss"] = stop
        reward = abs(target - entry)
        if reward <= 0:
            return False
        required_distance = reward / self.MIN_RR
        current_distance = abs(entry - stop)
        # Preserve stops already in the acceptable risk band; widen only
        # abnormally tight stops while keeping at least 1:1.25 reward/risk.
        if current_distance > 0 and current_distance >= required_distance:
            signal["risk_adjusted"] = False
            signal["estimated_risk"] = self.TARGET_RISK
            signal["risk_reward"] = reward / current_distance
            return signal["risk_reward"] >= self.MIN_RR
        if side == "BUY":
            signal["stop_loss"] = entry - required_distance
        elif side == "SELL":
            signal["stop_loss"] = entry + required_distance
        else:
            return False
        signal["risk_adjusted"] = True
        signal["estimated_risk"] = self.TARGET_RISK
        signal["risk_reward"] = reward / abs(entry - float(signal["stop_loss"]))
        return signal["risk_reward"] >= self.MIN_RR
