/*
 * Minimal harness that runs the original SWI-Prolog unification algorithm
 * through the public FLI entry point PL_unify().
 *
 * Trace format is the same binary format used by bench/trace.py:
 *   tag 0: var(int64 id)
 *   tag 1: int(int64)
 *   tag 2: float(raw IEEE-754 bits, little endian)
 *   tag 3: string(length:int64, bytes)
 *   tag 4: compound(functor_id:int64, arity:int64, args...)
 *
 * The parser and benchmark driver are local to this file.  Unification is
 * not reimplemented: every equation is solved by PL_unify(), i.e. the
 * original SWI-Prolog engine path:
 *   PL_unify -> unify_ptrs -> do_unify -> do_unify_compound.
 */

#define _GNU_SOURCE

#include <SWI-Prolog.h>

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <locale.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <sched.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* ------------------------------ util ---------------------------------- */

static void die(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
    exit(2);
}

static void *xmalloc(size_t n)
{
    void *p = malloc(n ? n : 1);
    if ( !p ) die("out of memory");
    return p;
}

static void *xrealloc(void *p, size_t n)
{
    void *q = realloc(p, n ? n : 1);
    if ( !q ) die("out of memory");
    return q;
}

/* ------------------------------ AST ----------------------------------- */

typedef enum {
    NODE_VAR,
    NODE_INT,
    NODE_FLOAT,
    NODE_STRING,
    NODE_COMPOUND
} NodeTag;

typedef struct Node Node;

struct Node {
    NodeTag tag;
    union {
        int64_t  var_id;
        int64_t  int_value;
        double   float_value;
        struct {
            char   *data;
            size_t  len;
        } str;
        struct {
            int64_t functor_id;
            size_t  arity;
            Node  **args;
        } compound;
    } u;
};

typedef struct {
    Node **left;
    Node **right;
    size_t count;
    size_t capacity;
    int64_t max_var_id;
} Trace;

static Node *new_node(NodeTag tag)
{
    Node *n = xmalloc(sizeof(*n));
    memset(n, 0, sizeof(*n));
    n->tag = tag;
    return n;
}

static uint8_t read_u8(FILE *f)
{
    int c = fgetc(f);
    if ( c == EOF ) die("unexpected end of trace");
    return (uint8_t)c;
}

static uint64_t read_u64le(FILE *f)
{
    uint8_t b[8];
    if ( fread(b, 1, 8, f) != 8 ) die("unexpected end of trace (int64)");
    uint64_t v = 0;
    for ( int i = 7; i >= 0; i-- )
        v = (v << 8) | b[i];
    return v;
}

static Node *parse_node(FILE *f, Trace *tr)
{
    uint8_t tag = read_u8(f);
    switch(tag)
    { case 0:
      { Node *n = new_node(NODE_VAR);
        n->u.var_id = (int64_t)read_u64le(f);
        if ( n->u.var_id < 0 ) die("negative variable id");
        if ( n->u.var_id > tr->max_var_id ) tr->max_var_id = n->u.var_id;
        return n;
      }
      case 1:
      { Node *n = new_node(NODE_INT);
        n->u.int_value = (int64_t)read_u64le(f);
        return n;
      }
      case 2:
      { Node *n = new_node(NODE_FLOAT);
        uint64_t bits = read_u64le(f);
        memcpy(&n->u.float_value, &bits, sizeof(double));
        return n;
      }
      case 3:
      { Node *n = new_node(NODE_STRING);
        uint64_t len = read_u64le(f);
        if ( len > SIZE_MAX ) die("string too long");
        n->u.str.len = (size_t)len;
        n->u.str.data = xmalloc(n->u.str.len + 1);
        if ( n->u.str.len && fread(n->u.str.data, 1, n->u.str.len, f) != n->u.str.len )
          die("unexpected end of trace (string)");
        n->u.str.data[n->u.str.len] = '\0';
        return n;
      }
      case 4:
      { Node *n = new_node(NODE_COMPOUND);
        n->u.compound.functor_id = (int64_t)read_u64le(f);
        uint64_t arity = read_u64le(f);
        if ( arity > SIZE_MAX / sizeof(Node *) ) die("arity too large");
        n->u.compound.arity = (size_t)arity;
        n->u.compound.args = xmalloc(n->u.compound.arity * sizeof(Node *));
        for ( size_t i = 0; i < n->u.compound.arity; i++ )
          n->u.compound.args[i] = parse_node(f, tr);
        return n;
      }
      default:
        die("invalid trace tag: %u", (unsigned)tag);
    }
    return NULL;
}

static Trace *parse_trace(const char *path)
{
    FILE *f = fopen(path, "rb");
    if ( !f ) die("cannot open trace %s: %s", path, strerror(errno));

    Trace *tr = xmalloc(sizeof(*tr));
    memset(tr, 0, sizeof(*tr));
    tr->capacity = 64;
    tr->left  = xmalloc(tr->capacity * sizeof(Node *));
    tr->right = xmalloc(tr->capacity * sizeof(Node *));

    for (;;)
    { int c;
      if ( (c=fgetc(f)) == EOF )
        break;
      if ( ungetc(c, f) == EOF )
        die("ungetc failed while parsing trace");
      Node *a = parse_node(f, tr);
      Node *b = parse_node(f, tr);

      if ( tr->count == tr->capacity )
      { tr->capacity *= 2;
        tr->left  = xrealloc(tr->left,  tr->capacity * sizeof(Node *));
        tr->right = xrealloc(tr->right, tr->capacity * sizeof(Node *));
      }
      tr->left[tr->count] = a;
      tr->right[tr->count] = b;
      tr->count++;
    }

    fclose(f);
    return tr;
}

/* --------------------------- WAM building ----------------------------- */

typedef struct {
    term_t *vars;
    size_t  var_count;
} BuiltTrace;

typedef struct {
    atom_t   atom;
    functor_t functor;
} FunctorCacheEntry;

typedef struct {
    FunctorCacheEntry *entries;
    size_t count;
    size_t capacity;
} FunctorCache;

static functor_t get_functor(FunctorCache *cache, int64_t id, size_t arity)
{
    char name[80];
    snprintf(name, sizeof(name), "f_%" PRId64, id);
    atom_t a = PL_new_atom(name);
    functor_t f = PL_new_functor(a, (int)arity);

    if ( cache->count == cache->capacity )
    { cache->capacity = cache->capacity ? cache->capacity * 2 : 64;
      cache->entries = xrealloc(cache->entries,
                                cache->capacity * sizeof(FunctorCacheEntry));
    }
    cache->entries[cache->count].atom = a;
    cache->entries[cache->count].functor = f;
    cache->count++;

    return f;
}

static term_t build_term(Node *n, BuiltTrace *bt, FunctorCache *fcache);

static term_t get_var(BuiltTrace *bt, int64_t id)
{
    if ( (size_t)id >= bt->var_count ) die("variable id out of range");
    if ( !bt->vars[id] )
    { bt->vars[id] = PL_new_term_ref();
      if ( !PL_put_variable(bt->vars[id]) ) die("PL_put_variable failed");
    }
    return bt->vars[id];
}

static term_t build_term(Node *n, BuiltTrace *bt, FunctorCache *fcache)
{
    term_t t = PL_new_term_ref();
    switch(n->tag)
    { case NODE_VAR:
        return get_var(bt, n->u.var_id);
      case NODE_INT:
        if ( !PL_put_integer(t, (long)n->u.int_value) ) die("PL_put_integer failed");
        return t;
      case NODE_FLOAT:
        if ( !PL_put_float(t, n->u.float_value) ) die("PL_put_float failed");
        return t;
      case NODE_STRING:
        if ( !PL_put_string_nchars(t, n->u.str.len, n->u.str.data) )
          die("PL_put_string_nchars failed");
        return t;
      case NODE_COMPOUND:
      { size_t arity = n->u.compound.arity;
        if ( arity > INT_MAX ) die("arity exceeds INT_MAX");
        term_t args = PL_new_term_refs(arity);
        for ( size_t i = 0; i < arity; i++ )
        { term_t sub = build_term(n->u.compound.args[i], bt, fcache);
          if ( !PL_put_term(args + i, sub) ) die("PL_put_term failed");
        }
        functor_t f = get_functor(fcache, n->u.compound.functor_id, arity);
        if ( !PL_cons_functor_v(t, f, args) ) die("PL_cons_functor_v failed");
        return t;
      }
    }
    die("unknown node tag");
    return 0;
}

/* Build all WAM terms within the current (outer) foreign frame. */
static term_t *g_left;
static term_t *g_right;
static size_t g_count;

static BuiltTrace build_wam_trace(Trace *tr)
{
    BuiltTrace bt;
    bt.var_count = (size_t)tr->max_var_id + 1;
    bt.vars = xmalloc(bt.var_count * sizeof(term_t));
    for ( size_t i = 0; i < bt.var_count; i++ ) bt.vars[i] = 0;

    FunctorCache fcache;
    memset(&fcache, 0, sizeof(fcache));

    term_t *left  = xmalloc(tr->count * sizeof(term_t));
    term_t *right = xmalloc(tr->count * sizeof(term_t));

    for ( size_t i = 0; i < tr->count; i++ )
    { left[i]  = build_term(tr->left[i],  &bt, &fcache);
      right[i] = build_term(tr->right[i], &bt, &fcache);
    }

    free(fcache.entries);

    g_left = left;
    g_right = right;
    return bt;
}

static term_t *g_left;
static term_t *g_right;
static size_t g_count;

static bool run_trace(void)
{
    for ( size_t i = 0; i < g_count; i++ )
    { if ( !PL_unify(g_left[i], g_right[i]) )
        return false;
    }
    return true;
}

/* ------------------------------ timing -------------------------------- */

static double now_seconds(void)
{
    struct timespec ts;
    if ( clock_gettime(CLOCK_MONOTONIC, &ts) != 0 ) die("clock_gettime failed");
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

/* --------------------------- CLI / main -------------------------------- */

typedef struct {
    const char *trace_file;
    bool check;
    bool quiet;
    int warmup;
    int samples;
    int iters;
    int cpu;
    bool cpu_set;
} Config;

static Config parse_args(int argc, char **argv)
{
    Config cfg = {0};
    cfg.warmup = 100;
    cfg.samples = 100;
    cfg.iters = 20;
    cfg.cpu = -1;
    cfg.cpu_set = false;

    for ( int i = 1; i < argc; i++ )
    { const char *a = argv[i];
      if ( !strcmp(a, "--check") ) cfg.check = true;
      else if ( !strcmp(a, "--quiet") ) cfg.quiet = true;
      else if ( !strcmp(a, "--warmup") && i+1 < argc ) cfg.warmup = atoi(argv[++i]);
      else if ( !strcmp(a, "--samples") && i+1 < argc ) cfg.samples = atoi(argv[++i]);
      else if ( !strcmp(a, "--iters") && i+1 < argc ) cfg.iters = atoi(argv[++i]);
      else if ( !strcmp(a, "--cpu") && i+1 < argc )
      { cfg.cpu = atoi(argv[++i]);
        cfg.cpu_set = (cfg.cpu >= 0);
      }
      else if ( !strcmp(a, "-q") || !strcmp(a, "--nosignals") || !strcmp(a, "--no-signals") )
        continue;
      else if ( a[0] == '-' )
      { fprintf(stderr, "unknown option: %s\n", a);
        exit(2);
      }
      else if ( !cfg.trace_file ) cfg.trace_file = a;
      else die("trace file already set");
    }

    if ( !cfg.trace_file ) die("trace file not set");
    return cfg;
}

static void dump_state(BuiltTrace *bt)
{
    for ( size_t i = 0; i < bt->var_count; i++ )
    { term_t v = bt->vars[i];
      if ( !v || PL_is_variable(v) ) continue;

      fid_t fid = PL_open_foreign_frame();
      term_t copy = PL_new_term_ref();
      if ( !PL_put_term(copy, v) ) die("PL_put_term failed in dump");
      char *s = NULL;
      if ( PL_get_chars(copy, &s, CVT_WRITE|BUF_MALLOC) )
      { printf("  %zu -> %s\n", i, s);
        PL_free(s);
      }
      PL_close_foreign_frame(fid);
    }
}

int main(int argc, char **argv)
{
    Config cfg = parse_args(argc, argv);

    char *swi_argv[] = { argv[0], (char *)"-q", (char *)"--nosignals", NULL };
    int swi_argc = 3;
    if ( !PL_initialise(swi_argc, swi_argv) )
      die("PL_initialise failed");

    /* Make %f output locale-independent for the benchmark scripts. */
    setlocale(LC_NUMERIC, "C");

    if ( cfg.cpu_set )
    { cpu_set_t mask;
      CPU_ZERO(&mask);
      CPU_SET(cfg.cpu, &mask);
      if ( sched_setaffinity(0, sizeof(mask), &mask) != 0 )
        die("sched_setaffinity(%d) failed: %s", cfg.cpu, strerror(errno));
    }

    PL_set_prolog_flag("occurs_check", PL_ATOM, "false");

    Trace *tr = parse_trace(cfg.trace_file);
    g_count = tr->count;

    fid_t outer = PL_open_foreign_frame();
    BuiltTrace bt = build_wam_trace(tr);

    if ( cfg.check )
    { fid_t run = PL_open_foreign_frame();
      bool ok = run_trace();
      PL_discard_foreign_frame(run);
      if ( !ok ) { fprintf(stderr, "unification failed\n"); return 1; }
      dump_state(&bt);
      printf("%zu\t0\n", bt.var_count);
      PL_discard_foreign_frame(outer);
      PL_halt(0);
      return 0;
    }

    if ( !cfg.quiet )
    { printf("Warm-up...\n");
      fflush(stdout);
    }

    for ( int i = 0; i < cfg.warmup; i++ )
    { fid_t run = PL_open_foreign_frame();
      (void)run_trace();
      PL_discard_foreign_frame(run);
    }

    if ( !cfg.quiet ) printf("Samples (ns):\n");

    for ( int s = 0; s < cfg.samples; s++ )
    { double span = 0.0;
      for ( int it = 0; it < cfg.iters; it++ )
      { fid_t run = PL_open_foreign_frame();
        double t0 = now_seconds();
        bool ok = run_trace();
        double t1 = now_seconds();
        PL_discard_foreign_frame(run);
        if ( !ok ) die("unification failed during benchmark");
        span += (t1 - t0);
      }
      double sample = span * 1e9 / (double)cfg.iters;
      printf("%d\t%.1f\n", s+1, sample);
      fflush(stdout);
    }

    PL_discard_foreign_frame(outer);
    PL_halt(0);
    return 0;
}
