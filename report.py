#!/usr/bin/env python3

import collections
import pathlib
import re
import tempfile
import zipfile

import click
import hytek_parser


@click.group()
def cli():
    """dolphins cli help text"""
    pass


def file_stream(top):
    path = pathlib.Path(top)
    for p in path.rglob("*"):
        if p.name.endswith(".zip"):
            archive = zipfile.ZipFile(p, "r")
            with tempfile.TemporaryDirectory() as tempdir:
                archive.extractall(tempdir)
                for zippath in pathlib.Path(tempdir).rglob("*"):
                    if zippath.suffix == ".hy3":
                        yield zippath
        elif p.suffix == ".hy3":
            yield p


def events(src):

    for afile in src:
        print(afile)
        ht = hytek_parser.parse_hy3(afile)

        for event in ht.meet.events.values():
            for entry in event.entries:
                if len(entry.swimmers) != 1:
                    # print(" skip multiswimmer event",y.stroke.name, y.distance)
                    continue
                for aswimmer in entry.swimmers:
                    yield {"swimmer": aswimmer, "entry": entry, "details": event}


@cli.command(name="compare")
@click.option("--dir", "adir", help="recurively search below")
def compare(adir):

    mem = collections.defaultdict(lambda: collections.defaultdict(dict))
    for event in events(file_stream(adir)):
        # if 'Cariaso' not in event['swimmer'].last_name:
        #    continue
        swimmer_key = (event["swimmer"].last_name, event["swimmer"].first_name)
        event_key = (event["details"].distance, event["details"].stroke.name)
        swim_date = event["entry"].finals_date
        final_time = event["entry"].finals_time
        # print(f"  :{event['details'].distance:>5d} {event['details'].stroke.name:<15s}: {event['entry'].finals_date} {event['entry'].finals_time:>10.2f} {event['swimmer'].first_name} {event['swimmer'].last_name}")
        mem[swimmer_key][event_key][swim_date] = final_time

    import matplotlib.pyplot as plt

    worst_times = {}
    best_times = {}
    for swimmer, swimmer_vals in mem.items():
        for event, event_vals in swimmer_vals.items():
            for swim_date, final_time in event_vals.items():
                if event not in worst_times:
                    worst_times[event] = final_time
                elif final_time > worst_times[event]:
                    worst_times[event] = final_time
                if event not in best_times:
                    best_times[event] = final_time
                elif final_time < best_times[event]:
                    best_times[event] = final_time

    for swimmer, swimmer_vals in sorted(mem.items()):
        for event, event_vals in swimmer_vals.items():

            if len(event_vals) > 1:

                x_label = []
                x = []
                y = []

                for swim_date, final_time in event_vals.items():
                    print(swimmer, event, swim_date, final_time)
                    x_label.append(swim_date)
                    y.append(final_time)
                x = list(range(len(x_label)))

                plt.clf()
                plt.plot(x, y)
                plt.ylim(ymin=best_times[event])
                plt.ylim(ymax=worst_times[event])

                plt.xticks(x, x_label, rotation="vertical")

                plt.title(f"{swimmer[0]} {swimmer[1]} {event}")
                filename_part = safe_filename(
                    f"{swimmer[0]}_{swimmer[1]}_{event[0]}_{event[1]}"
                )
                filename = f"images/{filename_part}.png"
                print(filename)
                plt.savefig(filename)


def safe_filename(filename):
    clean = re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F ]", "-", filename)
    return clean


if __name__ == "__main__":
    cli()
