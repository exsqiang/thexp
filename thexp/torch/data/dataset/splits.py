from typing import List, Tuple, Callable

import torch
from PIL import Image
from torch import randperm
from torch._utils import _accumulate
from torch.utils.data import Dataset, Subset


def sequence_split(dataset: Dataset, lengths: List[int]) -> List[Dataset]:
    """
    对应于 torch.utils.data.dataset.random_split ，用于按照长度顺序切分数据集
    Args:
        dataset:
        lengths:

    Returns:

    """
    indices = torch.arange(0, sum(lengths)).tolist()
    return [Subset(dataset, indices[offset - length:offset]) for offset, length in
            zip(_accumulate(lengths), lengths)]


def split_with_indices(dataset: Dataset, lengths: List[int], indices: List[int]) -> Tuple[List[Dataset], List[int]]:
    """
    Randomly split a dataset into non-overlapping new nddatasets of given lengths.

    Args:
        dataset: Dataset to be split
        lengths: lengths of splits to be produced
        indices: indices of dataset

    Returns:
        切分后的结果
    """
    if sum(lengths) != len(dataset):
        raise ValueError("Sum of input lengths does not equal the length of the input dataset!")

    return ([Subset(dataset, indices[offset - length:offset]) for offset, length in
             zip(_accumulate(lengths), lengths)], indices)


def semi_split(labels, n_percls, val_size=10000, include_sup=True):
    """
    在半监督的情况下切分训练集，有标签训练集和无标签训练集
    """
    import numpy as np
    labels = np.array(labels)
    n_cls = len({int(i) for i in labels})

    n_per_un = (len(labels) - val_size) // n_cls
    indexs = []
    un_indexs = []
    val_indexs = []
    for i in range(n_cls):
        idx = np.where(labels == i)[0]

        np.random.shuffle(idx)
        indexs.extend(idx[:n_percls])

        if include_sup:
            un_indexs.extend(idx[:n_per_un])  # 无标签样本部份也使用有标签样板
        else:
            un_indexs.extend(idx[n_percls:n_per_un])

        val_indexs.extend(idx[n_per_un:])

    # repeat
    indexs = np.hstack([indexs for i in range((len(un_indexs) // len(indexs)) + 1)])
    indexs = indexs[:len(un_indexs)]

    # shuffle indexs
    np.random.shuffle(indexs)
    np.random.shuffle(un_indexs)
    return indexs, un_indexs, val_indexs

def ratio2length(total_len, *ratios) -> List[int]:
    """
    将比率转换成具体整数值
    Args:
        total_len:  总长度
        *ratios:  任意长度比率，和不要求为1

    Returns:
        List[int]

    """
    return [int(total_len * i) for i in ratios]
