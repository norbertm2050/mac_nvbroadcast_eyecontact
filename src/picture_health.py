"""Flag sustained uniformly black input; a heuristic, never a reason to reset a camera."""


class PictureHealth:
    def __init__(self, grace=3):
        self.grace = grace
        self.black_since = None

    def update(self, mean, deviation, now, rgb=False):
        black = mean <= (3 if rgb else 17) and deviation < 1
        if not black:
            self.black_since = None
        elif self.black_since is None:
            self.black_since = now
        return self.black_since is not None and now - self.black_since >= self.grace
