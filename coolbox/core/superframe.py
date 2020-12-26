import abc
from collections import OrderedDict

import svgutils.compose as sc
import matplotlib.pyplot as plt

from coolbox.utilities import bool2str
from coolbox.utilities.figtools import cm2inch
from coolbox.utilities.filetool import get_uniq_tmp_file


class SuperFrame(abc.ABC):
    """Bigger frame composed by normal frames,
    compose figure using svgutils,
    this allow compose big figures which the matplotlib can not do.
    """
    def __init__(self, properties_dict):
        self.properties = bool2str(properties_dict)
        assert "sub_frames" in self.properties

    def plot_frames(self, frame2grange):
        """Plot each frame by a given GenomeRange object."""
        res = OrderedDict()
        for k, f in self.properties['sub_frames'].items():
            gr = frame2grange[k]
            path = get_uniq_tmp_file(prefix="frame_", suffix=".svg")
            fig = f.plot(gr)
            fig.subplots_adjust(wspace=0, hspace=0.0, left=0, right=1, bottom=0, top=1)
            fig.savefig(path)
            svg = sc.SVG(path)
            res[k] = svg
        return res


class JointView(SuperFrame):
    """Compose two track and a center matrix.

    https://github.com/GangCaoLab/CoolBox/issues/12

    Parameters
    ----------
    center : Track
        Center track for show 'contact map-like' plot,
        should has the '.plot_joint' method.

    top : Frame, optional
        Frame plot in the top of the center track.

    right : Frame, optional

    bottom : Frame, optional

    left : Frame, optional

    center_width : float
        The width of center track, unit in cm. default 20.

    trbl : str
        sub-frames(top right bottom left) use which genome range(first or second),
        default '1212', which means: top -> 1, right -> 2, bottom -> 1, left -> 2

    space : float
        Space between frame and center, unit in cm. default 0.5
    """

    def __init__(self, center,
                 top=None,
                 right=None,
                 bottom=None,
                 left=None,
                 **kwargs,
                 ):
        sub_frames = OrderedDict({
            "top": top,
            "right": right,
            "bottom": bottom,
            "left": left,
        })
        sub_frames = {k: v for k, v in sub_frames.items() if v is not None}

        self.__check_sub_frames(center, sub_frames)

        properties = {
            "sub_frames": sub_frames,
            "center_track": center,
            "center_width": 20,
            "trbl": "1212",
            "space": 1,
            "cm2px": 28.5,
            "padding_left": 1,
        }
        properties.update(**kwargs)

        super().__init__(properties)
        self.__adjust_sub_frames_width()

    @property
    def cm2px(self):
        return self.properties['cm2px']

    def __check_sub_frames(self, center, sub_frames):
        from .frame import Frame
        from .track.base import Track
        sub_f_names = ", ".join(sub_frames.keys())
        assert len(sub_frames) >= 2, f"At least one of {sub_f_names} should specified."
        if (not isinstance(center, Track)) and (not hasattr(center, "plot_joint")):
            raise TypeError("center should be a Track type instance with plot_joint method, "
                            "for example Cool, DotHiC, ...")
        for k, f in sub_frames.items():
            if not isinstance(f, Frame):
                if isinstance(f, Track):
                    sub_frames[k] = (Frame() + f)  # convert track to frame
                else:
                    raise TypeError(f"{sub_f_names} should be Frame object.")

    def __adjust_sub_frames_width(self):
        for k, f in self.properties['sub_frames'].items():
            width_ratios = f.properties['width_ratios']
            middle_ratio = width_ratios[1]
            new_width = self.properties['center_width'] / middle_ratio
            f.properties['width'] = new_width

    def plot_center(self, genome_range1, genome_range2):
        center_track = self.properties['center_track']
        size = cm2inch(self.properties['center_width'])
        fig, ax = plt.subplots(figsize=(size, size))
        center_track.plot_joint(ax, genome_range1, genome_range2)
        ax.set_axis_off()
        path = get_uniq_tmp_file(prefix='center', suffix='.svg')
        fig.subplots_adjust(wspace=0, hspace=0.0, left=0, right=1, bottom=0, top=1)
        fig.savefig(path)
        plt.close()
        return sc.SVG(path)

    def plot(self, genome_range1, genome_range2=None):
        """

        Parameters
        ----------
        genome_range1 : {str, GenomeRange}
            First genome range

        genome_range2 : {str, GenomeRange}, optional
            Second genome range
        """
        if genome_range2 is None:
            genome_range2 = genome_range1

        sub_frames = self.properties['sub_frames']
        trbl = self.properties['trbl']

        orientations = ['top', 'right', 'bottom', 'left']
        frame2grange = {
            k: (genome_range1 if (trbl[orientations.index(k)] == '1') else genome_range2)
            for k in orientations
        }
        frame_svgs = self.plot_frames(frame2grange)
        center_svg = self.plot_center(genome_range1, genome_range2)

        center_offsets = self.__get_center_offsets(sub_frames)

        center_svg.move(*[i*self.cm2px for i in center_offsets])
        self.__transform_sub_svgs(frame_svgs, sub_frames, center_offsets)

        figsize = self.__get_figsize(sub_frames)
        fig = sc.Figure(f"{figsize[0]*self.cm2px}px", f"{figsize[1]*self.cm2px}px",
                        sc.Panel(center_svg),
                        *[sc.Panel(svg) for svg in frame_svgs.values()])
        return fig

    def __transform_sub_svgs(self, sub_svgs, sub_frames, center_offsets):
        c_width = self.properties['center_width']
        space = self.properties['space']
        if 'top' in sub_svgs:
            s = sub_svgs['top']
            s.move(self.properties['padding_left']*self.cm2px, 0)
        if 'right' in sub_svgs:
            f = sub_frames['right']
            s = sub_svgs['right']
            s.rotate(90)
            wr = f.properties['width_ratios']
            right_offsets = [
                center_offsets[0] + c_width + f.properties['height'] + space,
                center_offsets[1] - f.properties['width']*wr[0]
            ]
            right_offsets = [i*self.cm2px for i in right_offsets]
            s.move(*right_offsets)

    def __get_center_offsets(self, sub_frames):
        space = self.properties['space']
        center_offsets = [self.properties['padding_left'], 0]  # x, y (left, top)
        if 'top' in sub_frames:
            f = sub_frames['top']
            center_offsets[0] += f.properties['width'] * f.properties['width_ratios'][0]
            center_offsets[1] += space + f.properties['height']
        if 'bottom' in sub_frames:
            f = sub_frames['bottom']
            if 'top' not in sub_frames:
                center_offsets[0] += f.properties['width'] * f.properties['width_ratios'][0]
        if 'left' in sub_frames:
            center_offsets[0] += space + sub_frames['left'].properties['height']
        return center_offsets

    def __get_figsize(self, sub_frames):
        space = self.properties['space']
        center_width = self.properties['center_width']
        size = [center_width, center_width]  # width, height
        if 'top' in sub_frames:
            f = sub_frames['top']
            size[0] = f.properties['width']
            size[1] += f.properties['height'] + space
        if 'bottom' in sub_frames:
            f = sub_frames['bottom']
            size[0] = f.properties['width']
            size[1] += f.properties['height'] + space
        if 'left' in sub_frames:
            f = sub_frames['left']
            size[0] += f.properties['height'] + space
        if 'right' in sub_frames:
            f = sub_frames['right']
            size[0] += f.properties['height'] + space
        self.properties['width'] = size[0]
        self.properties['height'] = size[1]
        return size

