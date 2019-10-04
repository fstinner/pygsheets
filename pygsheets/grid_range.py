from pygsheets.exceptions import InvalidArgumentValue, IncorrectCellLabel
import re


class Address(object):
    """
    Represents the address of a cell.
    This can also be unbound in an axes. So 'A' is also a valid address but this
    requires explict setting of param `allow_non_single`.
    Integer Indexes start from 1.

    >>> a = Address('A1')
    >>> a.label
    A1
    >>> a[0]
    1
    >>> a[1]
    1
    >>> a = Address((1, 1))
    >>> a.label
    A1
    >>> a + (0,1)
    <Address B1>
    >>> a == (1, 1)
    True
    """

    _MAGIC_NUMBER = 64

    def __init__(self, value, allow_non_single=False):
        self._is_single = True
        self.allow_non_single = allow_non_single

        if isinstance(value, str):
            self._value = self._label_to_coordinates(value)
        elif isinstance(value, tuple):
            assert len(value) == 2, 'tuple should be of length 2'
            assert type(value[0]) is int or value[0] is None, 'address row should be int'
            assert type(value[1]) is int or value[1] is None, 'address col should be int'
            self._value = value
            self._validate()
        elif not value and self.allow_non_single:
            self._value = (None, None)
            self._validate()
        elif isinstance(value, Address):
            self._value = self._label_to_coordinates(value.label)
        else:
            raise IncorrectCellLabel('Only labels in A1 notation, coordinates as a tuple or '
                                     'pygsheets.Address objects are accepted.')

    def is_valid_single(self):
        pass

    @property
    def label(self):
        """ Label of the current address in A1 format."""
        return self._value_as_label()

    @property
    def tuple(self):
        """Current Address in tuple format. Both axes starts at 1."""
        return tuple(self._value)

    def _validate(self):
        if not self.allow_non_single and (self._value[0] is None or self._value[0] is None):
            raise InvalidArgumentValue("Address cannot be unbounded if allow_non_single is not set.")

        if self._value[0]:
            row = int(self._value[0])
            if row < 1:
                raise InvalidArgumentValue('Address coordinates may not be below zero: ' + repr(self._value))

        if self._value[1]:
            col = int(self._value[1])
            if col < 1:
                raise InvalidArgumentValue('Address coordinates may not be below zero: ' + repr(self._value))

    def _value_as_label(self):
        """Transforms tuple coordinates into a label of the form A1."""
        self._validate()

        row_label, column_label = '', ''
        if self._value[0]:
            row_label = str(self._value[0])

        if self._value[1]:
            col = int(self._value[1])
            div = col
            column_label = ''
            while div:
                (div, mod) = divmod(div, 26)
                if mod == 0:
                    mod = 26
                    div -= 1
                column_label = chr(mod + self._MAGIC_NUMBER) + column_label

        return '{}{}'.format(column_label, row_label)

    def _label_to_coordinates(self, label):
        """Transforms a label in A1 notation into numeric coordinates and returns them as tuple."""
        m = re.match(r'([A-Za-z]*)(\d*)', label)
        if m:
            column_label = m.group(1).upper()
            row, col = m.group(2), 0
            if column_label:
                for i, c in enumerate(reversed(column_label)):
                    col += (ord(c) - self._MAGIC_NUMBER) * (26 ** i)
                col = int(col)
            else:
                col = None
            row = int(row) if row else None
        if not m or (not self.allow_non_single and not (row and col)):
            raise IncorrectCellLabel('Not a valid cell label format: {}.'.format(label))
        return row, col

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, str(self.label))

    def __iter__(self):
        return iter(self._value)

    def __getitem__(self, item):
        return self._value[item]

    def __setitem__(self, key, value):
        current_value = list(self._value)
        current_value[key] = value
        self._value = tuple(current_value)

    def __add__(self, other):
        if type(other) is tuple or isinstance(other, Address):
            return Address((self._value[0] + other[0], self._value[1] + other[1]))
        else:
            raise NotImplementedError

    def __sub__(self, other):
        if type(other) is tuple or isinstance(other, Address):
            return Address((self._value[0] - other[0], self._value[1] - other[1]))
        else:
            raise NotImplementedError

    def __eq__(self, other):
        if isinstance(other, Address):
            return self.label == other.label
        elif type(other) is str:
            return self.label == other
        elif type(other) is tuple or type(other) is list:
            return self._value == tuple(other)
        else:
            return super(Address, self).__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __bool__(self):
        return not (self._value[0] is None and self._value[1] is None)

    __nonzero__ = __bool__


class GridRange(object):
    """
    Represents a rectangular (can be unbounded) range of adresses on a sheet.
    All indexes are zero-based. Indexes are closed, e.g the start index and the end index is inclusive
    Missing indexes indicate the range is unbounded on that side.

    Reference: `GridRange API docs <https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/other#GridRange>`__

    """

    def __init__(self, label=None, worksheet=None, start=None, end=None, worksheet_title=None,
                 worksheet_id=None, namedjson=None):
        self._worksheet_title = worksheet_title
        self._worksheet_id = worksheet_id
        self._worksheet = worksheet
        self._label = label
        self._start = Address(start, True)
        self._end = Address(end, True)
        if namedjson:
            self.set_json(namedjson)
        elif label:
            self._calculate_addresses()
        else:
            self._apply_index_constraints()
            self._calculate_label()

    @property
    def start(self):
        """ address of top left cell (index) """
        return self._start

    @start.setter
    def start(self, value):
        self._start = Address(value, allow_non_single=True)
        self._apply_index_constraints()
        self._calculate_label()

    @property
    def end(self):
        """ address of bottom right cell (index) """
        return self._end

    @end.setter
    def end(self, value):
        self._end = Address(value, allow_non_single=True)
        self._apply_index_constraints()
        self._calculate_label()

    @property
    def indexes(self):
        """ Indexes of this range as a tuple """
        return self.start, self.end

    @indexes.setter
    def indexes(self, value):
        if type(value) is not tuple:
            raise InvalidArgumentValue("Please provide a tuple")
        self._start, self._end = Address(value[0], True), Address(value[1], True)
        self._apply_index_constraints()
        self._calculate_label()

    @property
    def label(self):
        """ Label in A1 notation format """
        return self._label

    @label.setter
    def label(self, value):
        if type(value) is not str:
            raise InvalidArgumentValue('non string value for label')
        self._label = value
        self._calculate_addresses()

    @property
    def worksheet_id(self):
        """ Id of woksheet this range belongs to """
        if self._worksheet:
            return self._worksheet.id
        return self._worksheet_id

    @worksheet_id.setter
    def worksheet_id(self, value):
        if self._worksheet:
            if self._worksheet.id == value:
                return
            else:
                raise InvalidArgumentValue("This range already has a worksheet with different id set.")
        self._worksheet_id = value

    @property
    def worksheet_title(self):
        """ Title of woksheet this range belongs to """
        if self._worksheet:
            return self._worksheet.title
        return self._worksheet_title

    @worksheet_title.setter
    def worksheet_title(self, value):
        if self._worksheet:
            if self._worksheet.title == value:
                return
            else:
                raise InvalidArgumentValue("This range already has a worksheet with different title set.")
        self._worksheet_title = value
        self._calculate_label()

    def set_worksheet(self, value):
        """ set the worksheet of this grid range. """
        self._worksheet = value
        self._worksheet_id = value.id
        self._worksheet_title = value.title
        self._calculate_label()

    def _apply_index_constraints(self, based_on='start'):
        if not self._start and not self._end:
            return

        if based_on == 'start':
            if not self._start:
                if self._end:
                    self._start = self._end
            elif self._start[0] is None or self._end[0] is None:
                self._start[0], self._end[0] = None, None
            elif self._start[1] is None or self._end[1] is None:
                self._start[1], self._end[1] = None, None
        elif based_on == 'end':
            if not self._end:
                if self._start:
                    self._end = self._start
            elif self._end[0] is None:
                self._start[0] = None
            elif self._end[1] is None:
                self._start[1] = None

        if (self._start[0] and not self._end[0]) or (not self._start[0] and self._end[0]) or \
           (self._start[1] and not self._end[1]) or (not self._start[1] and self._end[1]):
            self._start, self._end = (self._start, self._start) if based_on == 'start' else (self._end, self._end)
            raise InvalidArgumentValue('Invalid start and end set for this range')

        if self._start and self._end:
            if self._start[0]:
                assert self._start[0] <= self._end[0]
            if self._start[1]:
                assert self._start[1] <= self._end[1]

        self._calculate_label()

    def _calculate_label(self):
        """update label from values """
        label = self.worksheet_title
        label = '' if label is None else label
        if self._start and self._end:
            label += "!" + self._start.label + ":" + self._end.label
        self._label = label

    def _calculate_addresses(self):
        """ update values from label """
        label = self._label
        self.worksheet_title = label.split('!')[0]
        self._start, self._end = Address(None, True), Address(None, True)
        if len(label.split('!')) > 1:
            rem = label.split('!')[1]
            if ":" in rem:
                self._start = Address(rem.split(":")[0], allow_non_single=True)
                self._end = Address(rem.split(":")[1], allow_non_single=True)
            else:
                self._start = Address(rem, allow_non_single=True)
        self._apply_index_constraints()

    def to_json(self):
        """ Get json representation of this grid range. """
        if self.worksheet_id is None:
            raise Exception("worksheet id not set for this range.")
        self._calculate_addresses()
        return_dict = {"sheetId": self.worksheet_id}
        if self._start[0]:
            return_dict["startRowIndex"] = self._start[0] - 1
        if self._start[1]:
            return_dict["startColumnIndex"] = self._start[0]
        if self._end[0]:
            return_dict["endRowIndex"] = self._end[0] - 1
        if self._end[1]:
            return_dict["endColumnIndex"] = self._end[1]
        return return_dict

    def set_json(self, namedjson):
        """
        Apply a Gridrange json to this named range.

        :param namedjson: json object of the GridRange format

        Reference: `GridRange docs <https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/other#GridRange>`__
        """
        if 'sheetId' in namedjson:
            self.worksheet_id = namedjson['sheetId']
        start_row_idx = namedjson.get('startRowIndex', None)
        end_row_idx = namedjson.get('endRowIndex', None)
        start_col_idx = namedjson.get('startColumnIndex', None)
        end_col_idx = namedjson.get('endColumnIndex', None)
        start_row_idx = start_row_idx + 1 if start_row_idx is not None else start_row_idx
        start_col_idx = start_col_idx + 1 if start_col_idx is not None else start_col_idx
        self._start = Address((start_row_idx, start_col_idx), True)
        self._end = Address((end_row_idx, end_col_idx), True)
        self._calculate_label()

    def get_bounded_indexes(self):
        """ get bounded indexes of this range based on worksheet size, if the indexes are unbounded """
        if not self._worksheet:
            raise InvalidArgumentValue('Worksheet not set for calculating size.')
        start_r, start_c = tuple(iter(self.start)) if self.start else (None, None)
        end_r, end_c = tuple(iter(self.end)) if self.end else (None, None)
        start_r = start_r if start_r else 0
        start_c = start_c if start_c else 0
        end_r = end_r if end_r else self._worksheet.rows
        end_c = end_c if end_c else self._worksheet.cols
        return Address((start_r, start_c)), Address((end_r, end_c))

    @property
    def height(self):
        """ Height of this gridrange """
        start, end = self.get_bounded_indexes()
        return end[0] - start[0] + 1

    @property
    def width(self):
        """ Width of this gridrange """
        start, end = self.get_bounded_indexes()
        return end[1] - start[1] + 1

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, str(self.label))

    def __eq__(self, other):
        if isinstance(other, GridRange):
            return self.label == other.label
        elif type(other) is str:
            return self.label == other
        else:
            return super(GridRange, self).__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)
