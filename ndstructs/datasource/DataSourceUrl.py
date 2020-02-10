from urllib.parse import urlparse
from typing import Union, List, Tuple
from pathlib import Path
import re
import os
from functools import partial
import h5py
import z5py
import requests


class DataSourceUrl:
    H5_EXTENSIONS = ["h5", "hdf5", "ilp"]
    N5_EXTENSIONS = ["n5"]
    ARCHIVE_TYPES_REGEX = "|".join(H5_EXTENSIONS + N5_EXTENSIONS)
    NOT_FOLLOWED_BY_DOUBLE_SLASH = r"(?!//)"

    @classmethod
    def fetch_bytes(cls, url: str) -> bytes:
        print("Fetching ", url)
        if cls.is_remote(url):
            resp = requests.get(url)
            if resp.status_code == 404:
                raise FileNotFoundError(url)
            resp.raise_for_status()
            return resp.content
        else:
            data = bytes()
            with open(url, "rb") as f:
                data = f.read()
            return data

    @classmethod
    def is_remote(cls, url: str) -> bool:
        return urlparse(url).scheme not in ("file", "")

    @classmethod
    def split_archive_path(cls, path: Union[str, Path]) -> Tuple[Path, Path]:
        path = Path(path)
        if not cls.is_archive_path(path):
            raise ValueError(f"Path must be an archive path ({cls.ARCHIVE_TYPES_REGEX}). Provided: {path}")
        splitter = r"\.(" + cls.ARCHIVE_TYPES_REGEX + ")"
        external_path, extension, internal_path = re.split(splitter, path.absolute().as_posix(), re.IGNORECASE)
        return Path(external_path + "." + extension), Path(re.sub("^/", "", internal_path))

    @classmethod
    def is_archive_path(cls, path: Union[Path, str]) -> bool:
        # Any character after the trailing slash indicates something inside the archive
        ends_with_archive_extension = r"\.(" + cls.ARCHIVE_TYPES_REGEX + ")/."
        return bool(re.search(ends_with_archive_extension, Path(path).as_posix(), re.IGNORECASE))

    @classmethod
    def glob_to_regex(cls, glob: str) -> str:
        regex_star = "<REGEX_STAR>"
        return glob.replace("**", r"(?:\w|/)" + regex_star).replace("*", r"\w*").replace(regex_star, "*")

    @classmethod
    def sort_paths(cls, paths: List[Path]) -> List[Path]:
        return sorted(paths, key=lambda p: tuple(re.findall(r"[0-9]+", p.as_posix())))

    @classmethod
    def glob_archive_path(cls, path: Union[str, Path]) -> List[Path]:
        "Expands a path like /my/**/*/file.h5/some/**/*dataset* into all matching datasets in all matching files"

        external_path, internal_path = cls.split_archive_path(path)
        internal_regex = cls.glob_to_regex(internal_path.as_posix())
        dataset_paths: List[Path] = []

        def dataset_collector(
            inner_path: str, obj: Union[h5py.Group, h5py.Dataset, z5py.dataset.Dataset], prefix: Path
        ) -> None:
            if not isinstance(obj, (h5py._hl.dataset.Dataset, z5py.dataset.Dataset)):
                return
            if not re.match(internal_regex, inner_path):
                return
            dataset_paths.append(prefix / inner_path)

        for archive_path in cls.glob_fs_path(external_path):
            if archive_path.suffix.lower().replace(".", "") in cls.H5_EXTENSIONS:
                opener = partial(h5py.File, mode="r")
            else:
                opener = partial(z5py.File, mode="r")

            with opener(archive_path.as_posix()) as f:
                f.visititems(partial(dataset_collector, prefix=archive_path))

        return cls.sort_paths(dataset_paths)

    @classmethod
    def glob_fs_path(cls, path: Union[str, Path]) -> List[Path]:
        "Expands a path like /my/**/*/file.png into all matching files."

        if cls.is_archive_path(path):
            raise ValueError(f"path cannot be a path to data inside archive files: {path}")
        # FIXME: windows?
        rootless_glob = Path("/".join(Path(path).absolute().parts[1:])).as_posix()
        return cls.sort_paths(list(Path("/").glob(rootless_glob)))

    @classmethod
    def glob(cls, url: str, separator: str = os.path.pathsep + NOT_FOLLOWED_BY_DOUBLE_SLASH) -> List[str]:
        urls: List[str] = []
        for p in re.split(separator, url):
            path_item: str = p
            if cls.is_remote(path_item):
                urls.append(path_item)
            elif cls.is_archive_path(path_item):
                urls += [ap.as_posix() for ap in cls.glob_archive_path(path_item)]
            else:
                urls += [fsp.as_posix() for fsp in cls.glob_fs_path(path_item)]
        return urls  # do not resort so colon-separate globs maintain provided order
