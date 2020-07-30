from collections.abc import Iterable as CIterable
from itertools import chain
from typing import Callable, List, Union, Iterable

from torch.utils.data import Dataset


class _Value:
    """
    base class for a sample wrap
    """

    def __init__(self, value, name=None):
        self.value = value
        self.name = name


class X(_Value): pass


class Y(_Value): pass


class ID(_Value): pass


class Delegate:
    """
    对数据形式的代理

    一般而言，只使用DatasetBuilder已经足够表示所有的数据形式，但凡事总有例外。例如，如果要构造一个Triplet（一般包含
    一个锚样本（anchor），一个正例（positive），一个负例（negtive）），那么正例和负例样本的index和Dataset中要取的index
    是不一样的，此时没有很好的方法来实现在DatasetBuilder中构建Triplet三元组——除非继承另外实现，但我不喜欢这种方式，
    于是就诞生了Delegate类。

    Examples:
    --------
    你唯一需要的是根据你的需求在__init__() 中初始化变量，并重写 __call__() 方法，在其中构建你的数据形式
    
    class TripletDelegate(Delegate):
        def __init__(self, xs, ys, cls_num=10) -> None:
            super().__init__()
            self.xs = xs
            self.ys = ys
            self.id_dict = defaultdict(list)
            for i, target in enumerate(ys):
                self.id_dict[target].append(i)
            self.neg_cls_ids = [[i for i in range(cls_num) if i != j] for j in range(cls_num)]

        def __call__(self, index, builder=None) -> Union[X, Y, ID, None, Iterable[Value]]:
            pos_cls = self.ys[index]
            neg_cls = random.choice(self.neg_cls_ids[pos_cls])
            pos_id, neg_id = random.choice(self.id_dict[pos_cls]), random.choice(self.id_dict[neg_cls])
            pos_img = self.xs[pos_id]
            neg_img = self.xs[neg_id]

        return self.X_(pos_img), self.X_(neg_img), self.Y_(neg_cls)

    Notes:
    -------
    注意，你返回的数据因为需要识别是input（X）还是label（Y），因此你需要在你返回的数据外包裹一层Value的子类X/Y/ID 来
    辅助识别；这些子类已经在Delegate内部写好了包裹方法，即
    >>> self.X_(...), self.X_(...), self.Y_(...)

    当然，你也可以手动引入这三个类：
    >>> from thexp.frame.builder import X,Y,ID

    """

    def X_(self, value, name=None):
        """
        用于包裹数据，辅助 DatasetBuilder 识别
        Args:
            value: 作为X的单个样本
            name: 当 DatasetBuilder 的输出形式为dict时，名字是必需的

        Returns:
            X(value, name)
        """
        return X(value, name)

    def Y_(self, value, name=None):
        """
        用于包裹数据，辅助 DatasetBuilder 识别
        Args:
            value: 作为Y的单个标签
            name: 当 DatasetBuilder 的输出形式为dict时，名字是必需的

        Returns:
            X(value, name)
        """
        return Y(value, name)

    def ID_(self, value, name=None):
        """
        用于包裹数据，辅助 DatasetBuilder 识别
        Args:
            value: 作为 index 的单个序号
            name: 当 DatasetBuilder 的输出形式为dict时，名字是必需的

        Returns:
            X(value, name)
        """
        return ID(value, name)

    def __len__(self):
        return 0

    def __call__(self, index, builder=None) -> Union[X, Y, ID, None, Iterable[_Value]]:
        raise NotImplementedError()


class _placehold:
    """用于DatasetBuilder内部"""

    def __init__(self,
                 transform=None,
                 name=None, source=None, value=None):
        self.transform = transform
        self.name = name
        self.value = value
        self.source = source


class _delegate_placehold:
    """用于DatasetBuilder内部"""

    def __init__(self,
                 delegate: Delegate,
                 transform: Callable = None, target_transform: Callable = None,
                 name=None):
        self.delegate = delegate
        self.transform = transform
        self.target_transform = target_transform
        self.name = name


class DatasetBuilder(Dataset):
    """

    """

    def __init__(self, xs=None, ys=None, indices=None):
        self._dataset_len = None
        self._ipts = {}
        self._zip = False
        self._indices = indices
        self._re_indices = None
        self._placeholds = {'x': [], 'y': []}
        self._delegates = []  # type: List[_delegate_placehold]
        self._name = 'Dataset'
        self._source_names = set()
        self._data_names = set()
        self._delegate_names = set()
        self._add_id = False
        if xs is not None:
            self.add_inputs(xs)
        if ys is not None:
            self.add_labels(ys)

    def __str__(self):
        if self._zip:
            from thexp.base_classes.attr import attr
            res = attr()
            if self._add_id:
                res['ids'] = 'ids'
            for ph in chain(self._placeholds['x'], self._placeholds['y']):  # type:_placehold
                res[ph.name] = ph.source
            for dph in self._delegates:  # type: _delegate_placehold
                res[dph.name] = dph.delegate.__class__.__name__

            return str(res)
        else:
            ids = []
            xs = []
            ys = []
            deles = []
            if self._add_id:
                ids.append('ids')
            for ph in self._placeholds['x']:
                xs.append(ph.name)
            for ph in self._placeholds['y']:
                ys.append(ph.name)
            for dph in self._delegates:  # type: _delegate_placehold
                deles.append(dph.name)

            return str("{}: ({}, {}, {}, {})".format(
                self._name,
                ', '.join(ids),
                ', '.join(xs),
                ', '.join(ys),
                ', '.join(deles)))

    __repr__ = __str__

    def name(self, name: str):
        self._name = name
        return self

    def __len__(self) -> int:
        if self._re_indices is not None:
            return self.sample_num
        if self._indices is not None:
            return len(self._indices)
        return self._dataset_len

    def __getitem__(self, index: int):
        if self._re_indices is not None:
            if index >= self.real_num:
                index = index - self.real_num
                self._re_indices[index] = (self._re_indices[index] + self.vitu_num) % self.real_num
                index = self._re_indices[index]

        if self._indices is not None:
            index = self._indices[index]

        ids = []
        xs = []
        ys = []

        for ph in self._placeholds['x']:  # type:_placehold
            source = self._ipts[ph.source]
            x = source[index]
            if ph.transform is not None:
                x = ph.transform(x)
            ph.value = x
            xs.append(ph)
        for ph in self._placeholds['y']:
            source = self._ipts[ph.source]
            y = source[index]
            if ph.transform is not None:
                y = ph.transform(y)
            ph.value = y
            ys.append(ph)
        for dph in self._delegates:  # type:_delegate_placehold
            items = dph.delegate(index, self)
            if isinstance(items, _Value):
                items = [items]
            if isinstance(items, CIterable):
                for item in items:
                    assert isinstance(item, _Value)
                    if self._zip:
                        assert item.name is not None, 'value must have name in zip mode'

                    if isinstance(item, X):
                        if dph.transform is not None:
                            item.value = dph.transform(item.value)
                        xs.append(_placehold(name=item.name, value=item.value))
                    if isinstance(item, Y):
                        if dph.target_transform is not None:
                            item.value = dph.target_transform(item.value)
                        ys.append(_placehold(name=item.name, value=item.value))
                    if isinstance(item, ID):
                        ids.append(_placehold(name=item.name, value=item.value))

        if self._zip:
            from thexp.base_classes.attr import attr
            res = attr()
            if self._add_id:
                res['_indexs'] = index
            for ph in ids:
                res[ph.name] = ph.value
            for ph in xs:
                res[ph.name] = ph.value
            for ph in ys:
                res[ph.name] = ph.value

            return res
        else:
            ids = [i.value for i in ids]
            xs = [i.value for i in xs]
            ys = [i.value for i in ys]
            if self._add_id:
                ids.insert(0, index)

            return [*ids, *xs, *ys]

    def _check_len(self, values):
        ilen = len(values)
        if self._dataset_len is None:
            self._dataset_len = ilen
        else:
            assert self._dataset_len == ilen

    def _check_source_name(self, name):
        assert name not in self._source_names, 'source name "{}" duplicates'.format(name)
        self._source_names.add(name)

    def _check_data_name(self, name):
        assert name not in self._data_names, 'data name "{}" duplicates'.format(name)
        self._data_names.add(name)

    def _check_delegate_name(self, name):
        assert name not in self._delegate_names, 'delegate name "{}" duplicates'.format(name)
        self._delegate_names.add(name)

    def add_inputs(self, inputs, source_name='xs'):
        self._check_source_name(source_name)
        self._check_len(inputs)
        self._ipts[source_name] = inputs
        return self

    def add_labels(self, labels, source_name='ys'):
        self._check_source_name(source_name)
        self._check_len(labels)
        self._ipts[source_name] = labels
        return self

    def toggle_id(self, toggle=None):
        if toggle is None:
            toggle = not self._add_id
        self._add_id = toggle
        return self

    def add_x(self, transform=None, name=None, source='xs'):
        if name is None:
            name = 'input_{}'.format(len(self._placeholds['x']))
        self._check_data_name(name)
        self._placeholds['x'].append(_placehold(transform=transform, name=name, source=source))
        return self

    def add_y(self, transform=None, name=None, source='ys'):
        if name is None:
            name = 'label_{}'.format(len(self._placeholds['y']))

        self._check_data_name(name)
        self._placeholds['y'].append(_placehold(transform=transform, name=name, source=source))
        return self

    def add_delegate(self, delegate: Delegate, transform=None, target_transform=None, name=None):
        # self.d
        if name is None:
            name = 'delegate_{}'.format(len(self._delegates))
        self._check_delegate_name(name)
        self._check_len(delegate)
        self._delegates.append(_delegate_placehold(delegate, transform, target_transform, name))
        return self

    def zip_mode(self):
        self._zip = True
        return self

    def chain_mode(self):
        self.chain = True
        return self

    def subset(self, indices):
        self._indices = indices
        return self

    def virtual_sample(self, sample_num: int):
        self.sample_num = sample_num
        if self._indices is None:
            self.real_num = self._dataset_len
        else:
            self.real_num = len(self._indices)
        self.vitu_num = self.sample_num - self.real_num
        self._re_indices = list(range(self.sample_num - self.real_num))
        return self

    @staticmethod
    def DataLoader_from_dataset(dataset: Dataset, batch_size=1, shuffle=False, sampler=None,
                                batch_sampler=None, num_workers=0, collate_fn=None,
                                pin_memory=False, drop_last=False, timeout=0,
                                worker_init_fn=None, multiprocessing_context=None):
        from torch.utils.data import DataLoader
        return DataLoader(dataset=dataset,
                          batch_size=batch_size,
                          shuffle=shuffle,
                          sampler=sampler,
                          batch_sampler=batch_sampler,
                          num_workers=num_workers,
                          collate_fn=collate_fn,
                          pin_memory=pin_memory,
                          drop_last=drop_last,
                          timeout=timeout,
                          worker_init_fn=worker_init_fn,
                          multiprocessing_context=multiprocessing_context)

    def DataLoader(self, batch_size=1, shuffle=False, sampler=None,
                   batch_sampler=None, num_workers=0, collate_fn=None,
                   pin_memory=False, drop_last=False, timeout=0,
                   worker_init_fn=None, multiprocessing_context=None):
        from torch.utils.data import DataLoader
        return DataLoader(dataset=self,
                          batch_size=batch_size,
                          shuffle=shuffle,
                          sampler=sampler,
                          batch_sampler=batch_sampler,
                          num_workers=num_workers,
                          collate_fn=collate_fn,
                          pin_memory=pin_memory,
                          drop_last=drop_last,
                          timeout=timeout,
                          worker_init_fn=worker_init_fn,
                          multiprocessing_context=multiprocessing_context)
