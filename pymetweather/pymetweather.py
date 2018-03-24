import curses
import locale
from textwrap import fill
from datetime import date, timedelta

from pymetweather.forecasts import WeatherForecast
from pymetweather.get_args import get_command_line_args, get_config_args

locale.setlocale(locale.LC_ALL, '')


class WeatherPrinter(object):
    def __init__(self, forecast, screen_width):
        self.fcs = forecast

        self.cols = [
            (['Time'], 5, '{$:02}:00'),
            (['Conditions'], 22, '{W}'),
            (['Precipitation', 'probability'], 15, '{Pp:>3}\u2009%'),
            (['Temperature', '(Feels Like)'], 14, '{T:>2} {F}\u2009\u00b0C'),
            (['Wind Speed', '(Gust)'], 16, '{S:>2} {G}\u2009mph'),
            (['Wind', 'Direction'], 12, '{D:>3}'),
            (['Relative', 'Humidity'], 10, '{H}\u2009%'),
            (['Visibility'], 12, '{V}'),
            (['UV', 'Index'], 7, '{U}')]

        self.daily_cols = [
            (['Day'], 13, '{$}', '{$}'),
            (['Conditions'], 22, '{W}', '{W}'),
            (['Precipitation', 'probability'], 15,
             '{PPd:>3}\u2009%', '{PPn:>3}\u2009%'),
            (['Max day/', 'Min night', 'Temperature', '(Feels like)'], 14,
             '{Dm:>2} {FDm}\u2009\u00b0C', '{Nm:>2} {FNm}\u2009\u00b0C'),
            (['Wind Speed', '(Gust)'], 16,
             '{S:>2} {Gn}\u2009mph', '{S:>2} {Gm}\u2009mph'),
            (['Wind', 'Direction'], 12, '{D:>3}', '{D:>3}'),
            (['Relative', 'Humidity'], 10, '{Hn}\u2009%', '{Hm}\u2009%'),
            (['Visibility'], 12, '{V}', '{V}')]

        self.top_pad = curses.newpad(2000, 500)
        self.tab_pad = curses.newpad(2000, 500)
        self.bottom_bar = curses.newpad(1, 500)
        self.help_screen_pad = curses.newpad(500, 500)

        self.top_maxy = 0
        self.tab_maxy = 0
        self.tab_maxx = 0
        self.screen_width = screen_width
        self.print_bottom_bar()
        self.setup_help()

    @staticmethod
    def addustr(win, text, *args):
        win.addstr(text.encode('utf-8'), *args)

    def print_help_screen(self, top_only):
        if not top_only:
            self.addustr(self.tab_pad, self.help_string)
            self.tab_maxy = self.help_maxy
            self.tab_maxx = self.help_maxx

    def setup_help(self):
        help = [('q', 'Quit'),
                ('?', 'Show this help'),
                ('t', "Today's weather"),
                ('d', 'Five day summary'),
                ('0', "Today's weather"),
                ('1', "Tomorrow's weather"),
                ('2', 'Weather for 2 days later'),
                ('3', 'Weather for 3 days later'),
                ('4', 'Weather for 4 days later'),
                ('5\u20139', 'UK outlook for the next month'),
                ('l', 'UK outlook for the next month'),
                ('left arrow', 'scroll left'),
                ('right arrow', 'scroll left'),
                ('up arrow', 'scroll up'),
                ('down arrow', 'scroll down')]
        c1width = max([len(k[0]) for k in help])
        c2width = max([len(k[1]) for k in help])

        self.help_string = ''
        for h in help:
            self.help_string += h[0].ljust(c1width + 1) + ' : ' + h[1] + '\n'
        self.help_string = self.help_string.strip('\n')
        self.help_maxy = len(help) - 1
        self.help_maxx = c1width + c2width - 1

    def print_bottom_bar(self):
        self.addustr(
            self.bottom_bar, '?: help   q: quit   t: today   '
            'd: 5 day summary    1\u20134: days 1 to 4   '
            'l: longterm'.ljust(499),
            curses.A_REVERSE | curses.A_BOLD)

    def print_longer_term_weather(self):
        regf1 = self.fcs.reg_fcs[2]['Paragraph']
        regf2 = self.fcs.reg_fcs[3]['Paragraph']

        self.addustr(self.top_pad, self.wrap_text(regf1['title']),
                     curses.A_BOLD)
        self.addustr(self.top_pad, '\n' + self.wrap_text(regf1['$']) + '\n\n')
        self.addustr(
                self.top_pad, self.wrap_text(regf2['title']), curses.A_BOLD)
        self.addustr(self.top_pad, '\n' + self.wrap_text(regf2['$']))

        self.top_maxy = self.top_pad.getyx()[0]

    def wrap_text(self, text):
        return fill(text, self.screen_width)

    def print_hourly_top(self, n_day, day):
        title = 'Weather for {}, {}'.format(
            self.fcs.site_name, day.strftime('%A %d %B %Y'))
        self.addustr(self.top_pad, self.wrap_text(title) + '\n', curses.A_BOLD)

        regfindex = 0
        regf = self.fcs.reg_fcs[0]['Paragraph']
        if n_day == 0:
            if 'Headline' in regf[regfindex]['title']:
                self.addustr(self.top_pad, self.wrap_text(regf[regfindex]['$'])
                             + '\n\n')
                regfindex += 1

            if 'Today' in regf[regfindex]['title']:
                today_text = self.wrap_text('Today: ' + regf[regfindex]['$'])
                self.addustr(self.top_pad, today_text[:7], curses.A_BOLD)
                self.addustr(self.top_pad, today_text[7:] + '\n\n')
                regfindex += 1

            if 'Tonight' in regf[regfindex]['title']:
                tonight_text = self.wrap_text(regf[regfindex]['title'] + ' ' +
                                              regf[regfindex]['$'])
                lent = len(regf[regfindex]['title'])
                self.addustr(self.top_pad, tonight_text[:lent], curses.A_BOLD)
                self.addustr(self.top_pad, tonight_text[lent:] + '\n\n')
                regfindex += 1

        elif n_day == 1:
            for regfindex in range(len(regf)):
                if day.strftime('%A') in regf[regfindex]['title']:
                    self.addustr(self.top_pad,
                                 self.wrap_text(regf[regfindex]['$']) + '\n\n')
                    break
        else:
            regf = self.fcs.reg_fcs[1]['Paragraph']
            outlook = self.wrap_text(regf['title'] + ' ' + regf['$'])
            lent = len(regf['title']) + 1
            self.addustr(self.top_pad, '\n' + outlook[:lent], curses.A_BOLD)
            self.addustr(self.top_pad, outlook[lent:] + '\n\n')
        self.top_maxy = self.top_pad.getyx()[0]

    def print_hourly_tab(self, n_day, period):
        width_counter = 0
        for c in self.cols:
            for i, head in enumerate(c[0]):
                head_text = '{:^{}}'.format(head, c[1])
                self.tab_pad.move(i, width_counter)
                self.addustr(self.tab_pad, head_text, curses.A_BOLD)
            width_counter += c[1]
        top_row = (self.tab_pad.getyx()[0] +
                   max([len(c[0]) for c in self.cols]) - 1)
        for i, rep in enumerate(period['Rep']):
            width_counter = 0
            for c in self.cols:
                cell_text = '{:^{}}'.format(c[2].format(**rep), c[1])
                self.tab_pad.move(top_row + i, width_counter)
                self.addustr(self.tab_pad, cell_text)
                width_counter += c[1]
        self.tab_maxy = self.tab_pad.getyx()[0]
        self.tab_maxx = sum([c[1] for c in self.cols]) - 2

    def print_hourly_weather(self, n_day, top_only=False):
        day = date.today() + timedelta(n_day)
        period = self.fcs.hourly_fcs['Period'][n_day]
        assert period['value'] == day.strftime('%Y-%m-%dZ')

        self.print_hourly_top(n_day, day)
        if not top_only:
            self.print_hourly_tab(n_day, period)

    def print_weather_brief(self, top_only=False):
        period = self.fcs.daily_fcs['Period']

        width_counter = 0
        for c in self.daily_cols:
            for i, head in enumerate(c[0]):
                head_text = '{:^{}}'.format(head, c[1])
                self.tab_pad.move(i, width_counter)
                self.addustr(self.tab_pad, head_text, curses.A_BOLD)
            width_counter += c[1]
        top_row = (self.tab_pad.getyx()[0] +
                   max([len(c[0]) for c in self.daily_cols]))
        c = self.daily_cols[0]
        for i, rep in enumerate(period):
            cell_text = '{:<{}}   '.format(rep['value'], c[1] - 3)
            self.tab_pad.move(top_row + i * 4, 0)
            self.addustr(self.tab_pad, cell_text)

            cell_text = '{:>{}}   '.format(c[2].format(**rep['Rep'][0]),
                                            c[1] - 3)
            self.tab_pad.move(top_row + i * 4 + 1, 0)
            self.addustr(self.tab_pad, cell_text)

            cell_text = '{:>{}}   '.format(c[3].format(**rep['Rep'][1]),
                                            c[1] - 3)
            self.tab_pad.move(top_row + i * 4 + 2, 0)
            self.addustr(self.tab_pad, cell_text)

        for i, rep in enumerate(period):
            rep = rep['Rep']
            width_counter = self.daily_cols[0][1]
            for c in self.daily_cols[1:]:
                cell_text = '{:^{}}'.format(c[2].format(**rep[0]), c[1])
                self.tab_pad.move(top_row + i * 4 + 1, width_counter)
                self.addustr(self.tab_pad, cell_text)

                cell_text = '{:^{}}'.format(c[3].format(**rep[1]), c[1])
                self.tab_pad.move(top_row + i * 4 + 2, width_counter)
                self.addustr(self.tab_pad, cell_text)

                width_counter += c[1]

        self.tab_maxy = self.tab_pad.getyx()[0]
        self.tab_maxx = sum([c[1] for c in self.daily_cols]) - 2

    def print_screen(self, screen, screen_width=None, top_only=False):
        if screen_width is not None:
            self.screen_width = screen_width
        self.top_pad.clear()
        self.top_maxy = 0
        if not top_only:
            self.tab_maxy = 0
            self.tab_maxx = 0
            self.tab_pad.clear()
        if screen in range(0, 5):
            self.print_hourly_weather(screen, top_only)
        elif screen == 8:
            self.print_longer_term_weather()
        elif screen == 7:
            self.print_weather_brief(top_only)
        elif screen == 9:
            self.print_help_screen(top_only)


class WeatherApp(object):
    key_map = {
        '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
        '5': 8, '6': 8, '7': 8, '8': 8, '9': 9,
        't': 0,
        'l': 8,
        'd': 7,
        'b': 7,
        '?': 9}

    def __init__(self, stdscr, fcs, start_screen=0):
        self.stdscr = stdscr
        curses.curs_set(0)
        curses.use_default_colors()

        self.fcs = fcs

        self.scrolly = 0
        self.scrollx = 0
        self.maxy = 0
        self.maxx = 0

        self.y = self.stdscr.getmaxyx()[0] - 1
        self.x = self.stdscr.getmaxyx()[1] - 1

        self.printer = WeatherPrinter(self.fcs, self.x + 1)
        self.print_screen(start_screen)

    def print_resize(self):
        self.y = self.stdscr.getmaxyx()[0] - 1
        self.x = self.stdscr.getmaxyx()[1] - 1
        self.printer.print_screen(self.screen_showing, self.x + 1, True)

        self.maxx = max(self.printer.tab_maxx, self.x - 1)
        self.maxy = self.printer.tab_maxy + self.printer.top_maxy

        if self.y > (self.maxy - self.scrolly):
            self.scrolly = max(self.maxy - (self.y - 1), 0)
        if self.x > (self.maxx - self.scrollx):
            self.scrollx = max(self.maxx - (self.x - 1), 0)
        self.draw_screen()

    def print_screen(self, screen):
        self.screen_showing = screen
        self.scrolly = 0
        self.scrollx = 0
        self.printer.print_screen(self.screen_showing)

        self.maxy = self.printer.tab_maxy + self.printer.top_maxy
        self.maxx = max(self.printer.tab_maxx, self.x - 1)

        self.draw_screen()

    def draw_screen(self):
        self.stdscr.clear()
        self.stdscr.refresh()

        top_y = self.printer.top_maxy

        try:
            assert self.y == self.stdscr.getmaxyx()[0] - 1
            assert self.x == self.stdscr.getmaxyx()[1] - 1
        except AssertionError:
            self.print_resize()
            return

        self.printer.top_pad.noutrefresh(
            self.scrolly, 0, 0, 0, min(top_y, self.y), self.x)

        if self.y - (top_y - self.scrolly) > 1:
            self.printer.tab_pad.noutrefresh(
                max(0, self.scrolly - top_y), self.scrollx,
                top_y - self.scrolly, 0,
                self.y, self.x)

        self.printer.bottom_bar.noutrefresh(
            0, 0, self.y, 0, self.y, self.x)

        try:
            assert self.y == self.stdscr.getmaxyx()[0] - 1
            assert self.x == self.stdscr.getmaxyx()[1] - 1
        except AssertionError:
            self.print_resize()
            return

        with open('/tmp/log', 'a') as f:
            f.write('{}\t{}\t{}\t{}\t{}\t{}\n'.format(
                self.maxy, self.y, self.scrolly,
                self.maxx, self.x, self.scrollx))
        curses.doupdate()

    def main_loop(self):
        while True:
            c = self.stdscr.getkey()
            if c == 'q':
                return
            elif c in self.key_map and self.screen_showing != self.key_map[c]:
                self.print_screen(self.key_map[c])
            elif c == 'KEY_RESIZE':
                self.print_resize()
            elif c == 'KEY_DOWN':
                if self.scrolly + self.y - 1 < self.maxy:
                    self.scrolly += 1
                    self.draw_screen()
            elif c == 'KEY_UP' and self.scrolly != 0:
                self.scrolly -= 1
                self.draw_screen()
            elif c == 'KEY_LEFT' and self.scrollx != 0:
                self.scrollx -= 1
                self.draw_screen()
            elif c == 'KEY_RIGHT':
                if self.scrollx + self.x - 1 < self.maxx:
                    self.scrollx += 1
                    self.draw_screen()


def run_curses_app(screen, fcs):
    wap = WeatherApp(screen, fcs)
    wap.main_loop()


def run_app(args):
    fcs = WeatherForecast(args['api_key'], args['location'], args['datadir'])
    if args['quiet_update']:
        fcs.load(True)
        return
    fcs.load(args['dont_update'])
    fcs.process_forecast()
    curses.wrapper(run_curses_app, fcs)


def main():
    args = get_config_args()
    args.update(get_command_line_args())
    run_app(args)
