"""Console output"""
from asyncio import sleep, CancelledError
from shutil import get_terminal_size
from time import time
from sys import stdout, stderr

from nun._output import OutputBase

# ANSI shell colors
_COLORS = dict(RED=31, GREEN=32, YELLOW=33, BLUE=34, PINK=35, CYAN=36, GREY=37)


class Output(OutputBase):
    """Console output"""

    __slots__ = ('_width', '_clear')

    def __init__(self):
        # Initializes CLI output
        self._width = get_terminal_size()[0]
        self._clear = f'\r{self._width * " "}\r'

    def info(self, text):
        """
        Show info

        Args:
            text (str): text.
        """
        stdout.write(f'{self._clear}{text}\n')

    def warn(self, text):
        """
        Show warning

        Args:
            text (str): text.
        """
        stdout.write(f'{self._clear}\033[{_COLORS["YELLOW"]}m{text}\033[30m\n')

    def error(self, text):
        """
        Show error.

        Args:
            text (str): text.
        """
        stderr.write(f'{self._clear}\033[{_COLORS["RED"]}m{text}\033[30m\n')

    async def show_progress(self, files):
        """
        Show progression

        Args:
            files (iterable of nun._files.FileBase): Files in progress.
        """
        try:
            self.info('Operation started.')

            # Initialize progress bar
            bar_width = self._width - len(
                '\r Progress: || 000% | 000.0 KB / 000.0 KB | 000.0 KB/s  ')
            filled_width = 0
            percent = '?'
            total_formatted = '    ?  B'

            # Initialize size information
            full_size = 0
            files_sized = set()
            size_offset = 0
            prev_size = 0
            prev_time = time()

            # Initialize file completion information
            files_done = []

            # Show progress
            while files:
                size_done = size_offset
                approx = False

                # Check files in progress
                for file in files:
                    # Compute total operation size
                    if file not in files_sized:
                        size = file.size
                        if not size:
                            # Mark operation size as approximation
                            approx = True
                        else:
                            full_size += size
                            files_sized.add(file)

                    # Compute processed size
                    size_done += file.size_done

                    # Check if file is complete
                    if file.task.done():
                        files_done.append(file)

                # Show completed state for completed files
                while files_done:
                    file = files_done.pop()
                    files.remove(file)
                    size = file.size or file.size_done
                    if file not in files_sized:
                        full_size += size
                    size_offset += size
                    size, size_unit = self._get_unit(size)
                    if file.task.exception():
                        self.error(
                            f'- Errored: {file.resource_id}, {file.name},'
                            f' {file.task.exception()}')
                    else:
                        self.info(
                            f' - Completed: {file.resource_id}, {file.name},'
                            f' {size:>5.1f} {size_unit:>2}')

                # Set approximate progress information
                if not approx:
                    progress = size_done / (full_size or 1)
                    percent = int(progress * 100)
                    filled_width = int(bar_width * progress)
                    total, total_unit = self._get_unit(full_size)
                    total_formatted = f'{total:>5.1f} {total_unit:>2}'

                done, done_unit = self._get_unit(size_done)

                # Compute size process rate
                cur_time = time()
                rate = ((size_done - prev_size) / (cur_time - prev_time))
                if rate < 0.0:
                    rate = 0.0
                rate, rate_unit = self._get_unit(rate)

                # Print progress information
                stdout.write(
                    f'\rProgress: |{"█" * filled_width}'
                    f'{"-" * (bar_width - filled_width)}| {percent:>3}% '
                    f'| {done:>5.1f} {done_unit:>2} / {total_formatted} '
                    f'| {rate:>5.1f} {rate_unit:>2}/s  ')

                prev_size = size_done
                prev_time = cur_time
                await sleep(0.2)

            self.info('Operation completed.')
        except CancelledError:
            self.info('Operation cancelled.')
