from pathlib import Path

import pytest
import numpy as np

from ndstructs import Point5D, Slice5D, Array5D, Shape5D
from ndstructs.datasource.DataSource import ArrayDataSource
from ndstructs.datasource.DataSourceSlice import DataSourceSlice
from ndstructs.datasource.N5DataSource import N5DataSource
from ndstructs.datasink import N5DataSink


def test_n5_datasink(tmp_path: Path):
    data = Array5D(np.arange(20 * 10 * 7).reshape(20, 10, 7), axiskeys="xyz")
    ds = ArrayDataSource(data=data)
    dataset_path = tmp_path / "test_n5_datasink.n5/data"
    sink = N5DataSink(url=dataset_path, data_slice=DataSourceSlice(ds), tile_shape=Shape5D(x=10, y=10))
    sink.process(Slice5D.all())

    n5ds = N5DataSource(dataset_path)
    assert n5ds.retrieve(Slice5D.all()) == data


def test_n5_datasink_saves_roi(tmp_path: Path):
    data = Array5D(np.arange(20 * 10 * 7).reshape(20, 10, 7), axiskeys="xyz")
    ds = ArrayDataSource(data=data)
    roi = DataSourceSlice(ds, x=slice(5, 8), y=slice(2, 4))

    dataset_path = tmp_path / "test_n5_datasink.n5/data"
    sink = N5DataSink(url=dataset_path, data_slice=roi, tile_shape=Shape5D(x=10, y=10))
    sink.process(Slice5D.all())

    n5ds = N5DataSource(dataset_path)
    assert n5ds.retrieve(Slice5D.all()) == roi.retrieve()
