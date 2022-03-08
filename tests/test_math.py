from typing import Tuple

import numpy as np
import pytest
from affine import Affine

from odc.geo import XY, resxy_, xy_
from odc.geo.math import (
    Bin1D,
    affine_from_axis,
    align_down,
    align_up,
    apply_affine,
    data_resolution_and_offset,
    is_almost_int,
    maybe_int,
    maybe_zero,
    snap_affine,
    snap_scale,
    split_translation,
)
from odc.geo.testutils import mkA


def test_math_ops():
    assert align_up(32, 16) == 32
    assert align_up(31, 16) == 32
    assert align_up(17, 16) == 32
    assert align_up(9, 3) == 9
    assert align_up(8, 3) == 9

    assert align_down(32, 16) == 32
    assert align_down(31, 16) == 16
    assert align_down(17, 16) == 16
    assert align_down(9, 3) == 9
    assert align_down(8, 3) == 6

    assert maybe_zero(0, 1e-5) == 0
    assert maybe_zero(1e-8, 1e-5) == 0
    assert maybe_zero(-1e-8, 1e-5) == 0
    assert maybe_zero(0.1, 1e-2) == 0.1

    assert maybe_int(37, 1e-6) == 37
    assert maybe_int(37 + 1e-8, 1e-6) == 37
    assert maybe_int(37 - 1e-8, 1e-6) == 37
    assert maybe_int(3.4, 1e-6) == 3.4

    assert is_almost_int(129, 1e-6)
    assert is_almost_int(129 + 1e-8, 1e-6)
    assert is_almost_int(-129, 1e-6)
    assert is_almost_int(-129 + 1e-8, 1e-6)
    assert is_almost_int(0.3, 1e-6) is False


def test_snap_scale():
    assert snap_scale(0) == 0

    assert snap_scale(1 + 1e-6, 1e-2) == 1
    assert snap_scale(1 - 1e-6, 1e-2) == 1

    assert snap_scale(0.5 + 1e-8, 1e-3) == 0.5
    assert snap_scale(0.5 - 1e-8, 1e-3) == 0.5
    assert snap_scale(0.5, 1e-3) == 0.5

    assert snap_scale(0.6, 1e-8) == 0.6

    assert snap_scale(3.478, 1e-6) == 3.478


def test_data_res():
    xx = np.asarray([1, 2, 3, 4])
    assert data_resolution_and_offset(xx) == (1, 0.5)
    assert data_resolution_and_offset(xx[1:]) == (1, xx[1] - 1 / 2)
    assert data_resolution_and_offset(xx[:1], 1) == (1, 0.5)

    with pytest.raises(ValueError):
        data_resolution_and_offset(xx[:1])

    with pytest.raises(ValueError):
        data_resolution_and_offset(xx[:0])


def test_affine_from_axis():
    res = 10
    x0, y0 = 111, 212
    xx = np.arange(11) * res + x0 + res / 2
    yy = np.arange(13) * res + y0 + res / 2

    assert affine_from_axis(xx, yy) == Affine(res, 0, x0, 0, res, y0)

    assert affine_from_axis(xx, yy[::-1]) == Affine(
        res, 0, x0, 0, -res, yy[-1] + res / 2
    )

    # equivalent to y:-res, x:+res
    assert affine_from_axis(xx[:1], yy[:1], res) == Affine(
        res, 0, x0, 0, -res, y0 + res
    )
    assert affine_from_axis(xx[:1], yy[:1], resxy_(res, res)) == Affine(
        res, 0, x0, 0, res, y0
    )


def _check_bin(b: Bin1D, idx, tol=1e-8, nsteps=10):
    if isinstance(idx, int):
        idx = [idx]

    for _idx in idx:
        _in, _out = b[_idx]
        for x in np.linspace(_in + tol, _out - tol, nsteps):
            assert b.bin(x) == _idx


def test_bin1d_basic():
    b = Bin1D(sz=10, origin=20)
    assert b[0] == (20, 30)
    assert b[1] == (30, 40)
    assert b[-1] == (10, 20)
    assert b.bin(20) == 0
    assert b.bin(10) == -1
    assert b.bin(20 - 0.1) == -1

    for idx in [-3, -1, 0, 1, 2, 11, 23]:
        assert Bin1D.from_sample_bin(idx, b[idx], b.direction) == b

    _check_bin(b, [-3, 5])

    b = Bin1D(sz=10, origin=20, direction=-1)
    assert b[0] == (20, 30)
    assert b[-1] == (30, 40)
    assert b[1] == (10, 20)
    assert b.bin(20) == 0
    assert b.bin(10) == 1
    assert b.bin(20 - 0.1) == 1
    _check_bin(b, [-3, 5])

    assert Bin1D(10) == Bin1D(10, 0)
    assert Bin1D(10) == Bin1D(10, 0, 1)
    assert Bin1D(11) != Bin1D(10, 0, 1)
    assert Bin1D(10, 3) != Bin1D(10, 0, 1)
    assert Bin1D(10, 0, -1) != Bin1D(10, 0, 1)

    for idx in [-3, -1, 0, 1, 2, 11, 23]:
        assert Bin1D.from_sample_bin(idx, b[idx], b.direction) == b

    assert Bin1D(10) != ["something"]


def test_bin1d():
    _ii = [-3, -1, 0, 1, 2, 7]
    _check_bin(Bin1D(13.3, 23.5), _ii)
    _check_bin(Bin1D(13.3, 23.5, -1), _ii)


def test_apply_affine():
    A = mkA(rot=10, scale=(3, 1.3), translation=(-100, +2.3))
    xx, yy = np.meshgrid(np.arange(13), np.arange(11))

    xx_, yy_ = apply_affine(A, xx, yy)

    assert xx_.shape == xx.shape
    assert yy_.shape == xx.shape

    xy_expect = [A * (x, y) for x, y in zip(xx.ravel(), yy.ravel())]
    xy_got = list(zip(xx_.ravel(), yy_.ravel()))

    np.testing.assert_array_almost_equal(xy_expect, xy_got)


def test_split_translation():
    def verify(
        a: Tuple[XY[float], XY[float]],
        b: Tuple[XY[float], XY[float]],
    ):
        assert a[0].xy == pytest.approx(b[0].xy)
        assert a[1].xy == pytest.approx(b[1].xy)

    def tt(
        tx: float, ty: float, e_whole: Tuple[float, float], e_part: Tuple[float, float]
    ):
        expect = xy_(e_whole), xy_(e_part)
        rr = split_translation(xy_(tx, ty))
        verify(rr, expect)

    # fmt: off
    assert split_translation(xy_( 1,  2)) == (xy_( 1,  2), xy_(0, 0))
    assert split_translation(xy_(-1, -2)) == (xy_(-1, -2), xy_(0, 0))
    tt( 1.3, 2.5 , ( 1, 2), ( 0.3,  0.5 ))
    tt( 1.1, 2.6 , ( 1, 3), ( 0.1, -0.4 ))
    tt(-1.1, 2.8 , (-1, 3), (-0.1, -0.2 ))
    tt(-1.9, 2.05, (-2, 2), (+0.1,  0.05))
    tt(-1.5, 2.45, (-1, 2), (-0.5,  0.45))
    # fmt: on


def test_snap_affine():
    A = mkA(rot=0.1)
    assert snap_affine(A) is A

    assert snap_affine(mkA(translation=(10, 20))) == mkA(translation=(10, 20))

    assert snap_affine(mkA(translation=(10.1, 20.1)), ttol=0.2) == mkA(
        translation=(10, 20)
    )

    assert snap_affine(
        mkA(scale=(3.3, 4.2), translation=(10.1, 20.1)), ttol=0.2
    ) == mkA(scale=(3.3, 4.2), translation=(10, 20))

    assert snap_affine(
        mkA(scale=(3 + 1e-6, 4 - 1e-6), translation=(10.1, 20.1)), ttol=0.2, stol=1e-3
    ) == mkA(scale=(3, 4), translation=(10, 20))

    assert snap_affine(
        mkA(scale=(1 / 2 + 1e-8, 1 / 3 - 1e-8), translation=(10.1, 20.1)),
        ttol=0.2,
        stol=1e-3,
    ) == mkA(scale=(1 / 2, 1 / 3), translation=(10, 20))
