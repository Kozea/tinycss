#include <Python.h>


static PyObject *
tokenize_flat(PyObject *self, PyObject *args, PyObject *kwargs)
{
    int ignore_comments = 1;
    Py_ssize_t
        pos = 0, line = 1, column = 1, source_len, type, n_tokens, length,
        next_pos,
        COMMENT, BAD_COMMENT, DIMENSION, PERCENTAGE, NUMBER, IDENT,
        ATKEYWORD, HASH, FUNCTION, URI, STRING, BAD_STRING, DELIM;
    PyObject
        *css_source = NULL, *rv = NULL, *tokenizer_module = NULL,
        *compiled_tokens = NULL, *compiled_token_indexes = NULL,
        *unicode_unescape = NULL, *newline_unescape = NULL,
        *simple_unescape = NULL, *find_newlines = NULL, *Token = NULL,
        *item = NULL, *type_name = NULL, *DELIM_type_name = NULL,
        *tokens = NULL, *regexp = NULL, *match = NULL, *css_value = NULL,
        *value = NULL, *unit = NULL;

    #define CHECK(expr) { if(!(expr)) { goto error; } }

    static char *kwlist[] = {"css_source", "ignore_comments", NULL};
    CHECK(PyArg_ParseTupleAndKeywords(args, kwargs, "U|i", kwlist,
                                      &css_source, &ignore_comments));
    CHECK((source_len = PyUnicode_GetSize(css_source)) >= 0);
    CHECK(tokenizer_module = PyImport_ImportModule("tinycss.tokenizer"));

    #define GET_TOKENIZER_ATTR(variable, attr) CHECK( \
        variable = PyObject_GetAttrString(tokenizer_module, (attr)));

    GET_TOKENIZER_ATTR(compiled_tokens, "COMPILED_TOKEN_REGEXPS");
    GET_TOKENIZER_ATTR(compiled_token_indexes, "COMPILED_TOKEN_INDEXES");
    GET_TOKENIZER_ATTR(unicode_unescape, "UNICODE_UNESCAPE");
    GET_TOKENIZER_ATTR(newline_unescape, "NEWLINE_UNESCAPE");
    GET_TOKENIZER_ATTR(simple_unescape, "SIMPLE_UNESCAPE");
    GET_TOKENIZER_ATTR(find_newlines, "FIND_NEWLINES");
    GET_TOKENIZER_ATTR(Token, "Token");

    #define GET_TOKEN_INDEX(variable, name) { \
        CHECK(item = PyMapping_GetItemString(compiled_token_indexes, name)); \
        variable = PyNumber_AsSsize_t(item, NULL); \
        Py_DECREF(item); }

    GET_TOKEN_INDEX(COMMENT, "COMMENT");
    GET_TOKEN_INDEX(BAD_COMMENT, "BAD_COMMENT");
    GET_TOKEN_INDEX(DIMENSION, "DIMENSION");
    GET_TOKEN_INDEX(PERCENTAGE, "PERCENTAGE");
    GET_TOKEN_INDEX(NUMBER, "NUMBER");
    GET_TOKEN_INDEX(IDENT, "IDENT");
    GET_TOKEN_INDEX(ATKEYWORD, "ATKEYWORD");
    GET_TOKEN_INDEX(HASH, "HASH");
    GET_TOKEN_INDEX(FUNCTION, "FUNCTION");
    GET_TOKEN_INDEX(URI, "URI");
    GET_TOKEN_INDEX(STRING, "STRING");
    GET_TOKEN_INDEX(BAD_STRING, "BAD_STRING");
    DELIM = -1;
    DELIM_type_name = PyUnicode_FromString("DELIM");

    CHECK((n_tokens = PySequence_Length(compiled_tokens)) >= 0);
    CHECK(tokens = PyList_New(0));

    while (pos < source_len) {
        css_value = NULL;
        for (type = 0; type < n_tokens && css_value == NULL; type++) {
            CHECK(item = PySequence_GetItem(compiled_tokens, type));
            /* type_name and regexp are borrowed refs: */
            CHECK(PyArg_ParseTuple(item, "OO", &type_name, &regexp));
            CHECK(match = PyObject_CallFunction(regexp, "On", css_source, pos));
            if (match != Py_None) {
                /* First match is the longest. */
                CHECK(css_value = PyObject_CallMethod(match, "group", NULL));
                /* Take a ref not borrowed from item */
                Py_INCREF(type_name);
            } else {
                Py_DECREF(match);
            }
            Py_DECREF(item);
        }
        if (css_value == NULL) {
            /*
            No match.
            "Any other character not matched by the above rules,
             and neither a single nor a double quote."
            ... but quotes at the start of a token are always matched
            by STRING or BAD_STRING. So DELIM is any single character.
            */
            CHECK(css_value = PySequence_GetItem(css_source, pos));
            type = DELIM;
            type_name = DELIM_type_name;
            match = Py_None;
            Py_INCREF(type_name);
            Py_INCREF(match);
        }
        CHECK((length = PySequence_Length(css_value)) >= 0);
        next_pos = pos + length;

        value = css_value;
        unit = Py_None;
        Py_INCREF(unit);
        /* TODO: parse values and units */

        CHECK(item = PyObject_CallFunction(Token, "OOOOnn",
            type_name, css_value, value, unit, pos, pos));
        CHECK(PyList_Append(tokens, item) == 0);
        /* XXX does PyList_Append make a new ref to item? */
        /*Py_DECREF(item);*/

        pos = next_pos;

        Py_DECREF(type_name);
        Py_DECREF(match);
    }

    rv = tokens;

error:
    /* css_source is a reference borrowed from the caller,
       type_name and regexp from an 'item' tuple. */
    /* The reference to rv is trasfered to the caller. */
    Py_XDECREF(tokenizer_module);
    Py_XDECREF(compiled_tokens);
    Py_XDECREF(compiled_token_indexes);
    Py_XDECREF(unicode_unescape);
    Py_XDECREF(newline_unescape);
    Py_XDECREF(simple_unescape);
    Py_XDECREF(find_newlines);
    Py_XDECREF(Token);
    Py_XDECREF(item);
    Py_XDECREF(DELIM_type_name);
    Py_XDECREF(match);
    Py_XDECREF(css_value);

    return rv;
}


static PyMethodDef SpeedupsMethods[] = {
     {"tokenize_flat", (PyCFunction)tokenize_flat,
        METH_VARARGS | METH_KEYWORDS, "C version of tokenize_flat."},
     {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
init_speedups(void)
{
     (void) Py_InitModule("tinycss.tokenizer._speedups", SpeedupsMethods);
}
