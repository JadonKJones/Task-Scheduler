import pygame
import sys
import os
import array
from collections import deque

# --- Configuration & Styling ---
BG_COLOR = (13, 15, 23)
CARD_COLOR = (26, 30, 44)
TEXT_COLOR = (220, 225, 235)
ACCENT_BLUE = (0, 157, 255)  # WORKING
ACCENT_ORANGE = (255, 152, 0)  # READY
ACCENT_GREEN = (0, 230, 118)  # DONE
ACCENT_PURPLE = (187, 134, 252)  # RESTING
ACCENT_RED = (255, 82, 82)  # SWITCHING
CARD_BORDER = (45, 52, 71)

# Task setup
if not os.path.exists("tasks.txt"):
    with open("tasks.txt", "w") as f:
        f.write("CSE 325 Lab\nCSE 335 C++ Project\nSpanish Vocab\nJapanese N5 Anki")


def generate_beep_sound():
    """Generates a simple square wave beep for notifications."""
    pygame.mixer.init(frequency=44100, size=-16, channels=1)
    sample_rate = 44100
    freq = 587.33  # D5 note
    duration = 0.3
    n_samples = int(sample_rate * duration)
    buf = array.array('h', [0] * n_samples)
    for i in range(n_samples):
        t = i / sample_rate
        sample = 16000 if (int(2 * freq * t) % 2 == 0) else -16000
        buf[i] = int(sample * (1 - i / n_samples))  # Fade out
    return pygame.mixer.Sound(buf)


class Task:
    def __init__(self, name, task_id, is_rest=False):
        self.task_id = task_id
        self.name = name
        self.is_rest = is_rest
        self.total_seconds = 0
        self.rect = pygame.Rect(0, 0, 1, 1)


class InterleavingScheduler:
    def __init__(self):
        self.ready_q = deque()
        self.running_q = deque()
        self.halted_q = deque()

        # Real logic: 15min Work (900s), 1min Switch (60s), 15min Big Rest (900s)
        self.work_limit = 15 * 60
        self.switch_limit = 1 * 60
        self.big_rest_limit = 15 * 60

        self.elapsed = 0
        self.state = "WORKING"

        with open("tasks.txt", "r") as f:
            lines = [line.strip() for line in f if line.strip()]
            for i, name in enumerate(lines):
                self.ready_q.append(Task(name, i + 1))

        self.ready_q.append(Task("RECHARGE (Big Rest)", 999, is_rest=True))

    def update(self, seconds_to_add):
        """Advances the internal clock by a specific amount of seconds."""
        if not self.running_q and self.ready_q:
            self.dispatch_next()

        if self.running_q:
            current = self.running_q[0]
            self.elapsed += seconds_to_add
            current.total_seconds += seconds_to_add

            limit = self.work_limit
            if self.state == "SWITCHING":
                limit = self.switch_limit
            elif self.state == "RESTING":
                limit = self.big_rest_limit

            if self.elapsed >= limit:
                return True
        return False

    def dispatch_next(self):
        if self.ready_q:
            p = self.ready_q.popleft()
            self.running_q.append(p)
            self.elapsed = 0
            self.state = "RESTING" if p.is_rest else "WORKING"

    def start_switch(self):
        self.state = "SWITCHING"
        self.elapsed = 0

    def context_switch(self):
        if self.running_q:
            p = self.running_q.popleft()
            self.ready_q.append(p)
            self.dispatch_next()

    def complete_task(self, task):
        if task in self.running_q:
            self.running_q.remove(task)
            self.dispatch_next()
        elif task in self.ready_q:
            self.ready_q.remove(task)
        self.halted_q.append(task)


def main():
    pygame.init()
    beep = generate_beep_sound()

    screen = pygame.display.set_mode((1200, 800), pygame.RESIZABLE)
    pygame.display.set_caption("Jadon's Interleaving Scheduler")

    clock = pygame.time.Clock()
    sim = InterleavingScheduler()

    # SPEED SETTING: 1 real second = 60 virtual seconds
    # So we tick every 16ms (60fps) and add 1 virtual second per frame.
    VIRTUAL_SECONDS_PER_FRAME = 1

    while True:
        w, h = screen.get_size()
        screen.fill(BG_COLOR)
        mouse_pos = pygame.mouse.get_pos()

        # 1. Logic Update
        if sim.update(VIRTUAL_SECONDS_PER_FRAME):
            beep.play()
            if sim.state == "WORKING":
                sim.start_switch()
            else:
                sim.context_switch()

        # 2. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit();
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            if event.type == pygame.MOUSEBUTTONDOWN:
                for t in list(sim.ready_q) + list(sim.running_q):
                    if t.rect.collidepoint(mouse_pos) and not t.is_rest:
                        sim.complete_task(t)

        # 3. UI Drawing
        col_w = w // 3
        font_main = pygame.font.SysFont("Verdana", int(h * 0.022))
        font_bold = pygame.font.SysFont("Verdana", int(h * 0.032), bold=True)
        font_timer = pygame.font.SysFont("Courier New", int(h * 0.045), bold=True)

        # Header Display
        state_map = {"WORKING": ACCENT_BLUE, "SWITCHING": ACCENT_RED, "RESTING": ACCENT_PURPLE}
        current_color = state_map.get(sim.state, TEXT_COLOR)

        mins, secs = divmod(int(sim.elapsed), 60)
        timer_str = f"{sim.state}: {mins:02d}:{secs:02d}"

        # Draw background header bar
        pygame.draw.rect(screen, CARD_COLOR, (0, 0, w, 70))
        header_surf = font_timer.render(timer_str, True, current_color)
        screen.blit(header_surf, (w // 2 - header_surf.get_width() // 2, 15))

        # Column Labels
        cols = [("READY QUEUE", sim.ready_q, ACCENT_ORANGE, 0),
                ("CURRENT ACTION", sim.running_q, ACCENT_BLUE, col_w),
                ("COMPLETED", sim.halted_q, ACCENT_GREEN, col_w * 2)]

        for title, q, color, x_pos in cols:
            title_surf = font_bold.render(title, True, color)
            screen.blit(title_surf, (x_pos + 40, 90))

            for i, task in enumerate(list(q)):
                card_h = h // 8
                card_rect = pygame.Rect(x_pos + 30, 140 + (i * (card_h + 15)), col_w - 60, card_h)
                task.rect = card_rect

                # Card Shadow/Glow
                if title == "CURRENT ACTION":
                    glow_rect = card_rect.inflate(6, 6)
                    pygame.draw.rect(screen, current_color, glow_rect, border_radius=18)

                pygame.draw.rect(screen, CARD_COLOR, card_rect, border_radius=15)

                # Text inside cards
                name_surf = font_main.render(task.name, True, TEXT_COLOR)
                t_mins, t_secs = divmod(int(task.total_seconds), 60)
                time_surf = font_main.render(f"Logged: {t_mins}m {t_secs}s", True, (140, 150, 170))

                screen.blit(name_surf, (card_rect.x + 20, card_rect.y + 15))
                screen.blit(time_surf, (card_rect.x + 20, card_rect.y + card_rect.height - 35))

        pygame.display.flip()
        clock.tick(60)  # 60 FPS


if __name__ == "__main__":
    main()