from slp2mp4.scoreboard import scoreboard

from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager


_MONO_FONT_PROPS = font_manager.FontProperties(
    family=["Inconsolata", "Consolas", "monospace"],
)

# TODO: Clean this up. Like a lot.
class GameInfoPanel(scoreboard.ScoreboardPanel):
    def draw(self, png_path, height, context_data, game_index):
        y = 0
        foreground_color = (255, 255, 255)
        width = self.get_width(height)
        padding = height // 200
        size = (width, height)
        self.name = png_path
        # For some reason, using RGBA makes the text look bold
        self.image = Image.new("RGB", size)
        draw = ImageDraw.Draw(self.image)
        font_path = font_manager.fontManager.findfont(_MONO_FONT_PROPS)
        big_font = ImageFont.truetype(font_path, height // 12)
        regular_font = ImageFont.truetype(font_path, height // 24)

        # Top
        y += padding
        (_, _, _, y) = scoreboard.draw_multiline_text(
            y,
            padding,
            width,
            draw,
            context_data["startgg"]["tournament"]["name"],
            font=big_font,
            fill=foreground_color,
        )
        y += padding

        draw.line(
            ((padding, y), (width - padding, y)),
            fill=foreground_color,
            width=height // 480,
        )
        y += padding

        # Bottom

        y = height - padding
        (_, y, _, _) = scoreboard.draw_multiline_text(
            y,
            padding,
            width,
            draw,
            f"Best of {context_data['bestOf']}",
            align="left",
            anchor="bottom",
            font=regular_font,
            fill=foreground_color,
        )
        y -= padding

        (_, y, _, _) = scoreboard.draw_multiline_text(
            y,
            padding,
            width,
            draw,
            context_data["startgg"]["set"]["fullRoundText"],
            align="left",
            anchor="bottom",
            font=regular_font,
            fill=foreground_color,
        )
        y -= padding

        draw.line(
            ((padding, y), (width - padding, y)),
            fill=foreground_color,
            width=height // 480,
        )
        y -= padding

        (_, y, _, _) = scoreboard.draw_multiline_text(
            y,
            padding,
            width,
            draw,
            scoreboard.get_name_and_score_from_slot_data(
                context_data["scores"][game_index]["slots"][1]
            ),
            align="left",
            anchor="bottom",
            font=regular_font,
            fill=foreground_color,
        )
        y -= padding

        (_, y, _, _) = scoreboard.draw_multiline_text(
            y,
            padding,
            width,
            draw,
            scoreboard.get_name_and_score_from_slot_data(
                context_data["scores"][game_index]["slots"][0]
            ),
            align="left",
            anchor="bottom",
            font=regular_font,
            fill=foreground_color,
        )
        y -= padding

        draw.line(
            ((padding, y), (width - padding, y)),
            fill=foreground_color,
            width=height // 480,
        )
        y -= padding


class DefaultScoreboard(scoreboard.Scoreboard):
    def _get_scoreboard_panels(self):
        return [
            GameInfoPanel(606 / 1080)
        ]

    def _get_scoreboard_args(self):
        return ("[2][scaled]hstack=inputs=2",)
