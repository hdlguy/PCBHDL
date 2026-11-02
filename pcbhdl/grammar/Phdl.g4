// ANTLR 4 grammar for PHDL 2.1 (PCB Hardware Description Language).
//
// Written from the PHDL 2.1 language definition so that existing PHDL 2.1
// designs parse unchanged. The parser accepts a slightly larger language
// than is semantically valid; the elaborator enforces the remaining rules
// so that it can produce specific, helpful error messages.
//
// Regenerate the Python parser with:  python tools/gen_parser.py

grammar Phdl;

// ---------------------------------------------------------------------------
// Top level
// ---------------------------------------------------------------------------

model
    : importDecl* (packageDecl | device | design)* EOF
    ;

packageDecl
    : 'package' name=ID '{' importDecl* (device | design)* '}'
    ;

importDecl
    : 'import' qualifiedName ('.' wildcard='*')? ';'
    ;

// ---------------------------------------------------------------------------
// Devices
// ---------------------------------------------------------------------------

device
    : 'device' name=phdlId '{' deviceElement* '}'
    ;

deviceElement
    : attr
    | pinDecl
    | info
    ;

attr
    : 'attr' name=ID '=' value=STRING ';'
    ;

pinDecl
    : pinType vector? name=phdlId '=' '{' (phdlId (',' phdlId)*)? '}' ';'
    ;

pinType
    : 'pin'
    | 'inpin'
    | 'outpin'
    | 'iopin'
    | 'pwrpin'
    | 'suppin'
    | 'ocpin'
    | 'oepin'
    | 'tripin'
    | 'passpin'
    | 'ncpin'
    ;

info
    : 'info' '{' value=STRING '}'
    ;

// ---------------------------------------------------------------------------
// Designs
// ---------------------------------------------------------------------------

design
    : kind=('design' | 'subdesign') name=ID '{' designElement* '}'
    ;

designElement
    : connectionDecl
    | instance
    | connectionAssign
    | info
    ;

// 'net' and 'port' declarations. Ports may only carry 'info' elements;
// that restriction is checked by the elaborator.
connectionDecl
    : kind=('net' | 'port') vector? phdlId (',' phdlId)*
      ( '{' (attr | info)* '}' | ';' )
    ;

instance
    : 'inst'    array? name=ID 'of' ref=qualifiedName
      '{' instanceElement* '}'                                  # deviceInstance
    | 'subinst' array? name=ID 'of' ref=qualifiedName prefix=STRING?
      '{' subInstanceElement* '}'                               # subDesignInstance
    ;

instanceElement
    : attr
    | newAttr
    | refAttr
    | pinAssign
    | info
    ;

subInstanceElement
    : attr
    | subAttr
    | portAssign
    | info
    ;

// PHDL 2.0 spelling of a new instance attribute; accepted for
// compatibility and reported as deprecated.
newAttr
    : 'newattr' name=ID '=' value=STRING ';'
    ;

// Override of an attribute on (some elements of) a device instance.
refAttr
    : qualifier? name=ID '=' value=STRING ';'
    ;

// Override of an attribute on something inside a sub-design instance:
//   [this(i).] inst[(indices)] . ... . ATTR = "value";
subAttr
    : qualifier? name=ID indices? refTail '=' value=STRING ';'
    ;

refTail
    : '.' name=ID indices? refTail?
    ;

pinAssign
    : ( combine='combine' '(' qualifier? phdlId slices? ')'
      | qualifier? phdlId slices?
      ) '=' concatenation ';'
    ;

portAssign
    : ( combine='combine' '(' qualifier? phdlId slices? ')'
      | qualifier? phdlId slices?
      ) '=' concatenation ';'
    ;

connectionAssign
    : phdlId slices? '=' concatenation ';'
    ;

concatenation
    : '{' connectionRef (',' connectionRef)* '}'    # listConcat
    | connectionRef ('&' connectionRef)*            # ampConcat
    | '<' connectionRef '>'                         # replicateConcat
    | connectionRef '*'                             # starReplicateConcat
    | 'open'                                        # openConcat
    ;

connectionRef
    : phdlId slices?
    ;

// ---------------------------------------------------------------------------
// Ranges and qualifiers
// ---------------------------------------------------------------------------

// Instance-array element selection:  (msb:lsb)  or  (i, j, k)
indices
    : '(' msb=INT ':' lsb=INT ')'                   # indexRange
    | '(' INT (',' INT)* ')'                        # indexList
    ;

// Bit selection on vectors:  [msb:lsb]  or  [i, j, k]
slices
    : '[' msb=INT ':' lsb=INT ']'                   # sliceRange
    | '[' INT (',' INT)* ']'                        # sliceList
    ;

vector
    : '[' msb=INT ':' lsb=INT ']'
    ;

array
    : '(' msb=INT ':' lsb=INT ')'
    ;

qualifier
    : 'this' indices '.'
    ;

qualifiedName
    : phdlId ('.' phdlId)?
    ;

// Identifiers for devices, pins and nets may also be pin-number-like
// tokens such as 42, 1A, +3V3 or A/B.
phdlId
    : ID
    | INT
    | PINNUM
    ;

// ---------------------------------------------------------------------------
// Lexer
// ---------------------------------------------------------------------------

// Comments come first: '/' is legal inside PINNUM, so a comment such as
// "//GND" is the same length as a PINNUM and must win the tie.
ML_COMMENT : '/*' .*? '*/'                  -> channel(HIDDEN) ;
SL_COMMENT : '//' ~[\r\n]*                  -> channel(HIDDEN) ;
WS         : [ \t\r\n]+                     -> channel(HIDDEN) ;

ID      : [a-zA-Z_] [a-zA-Z_0-9]* ;
INT     : [0-9] | [1-9] [0-9]+ ;
PINNUM  : [0-9a-zA-Z_+\-$/@!]+ ;

STRING
    : '"'  ( '\\' [btnfru"'\\] | ~[\\"]  )* '"'
    | '\'' ( '\\' [btnfru"'\\] | ~[\\'] )* '\''
    ;

// Anything else is a lexical error; keeping it as a token lets the parser
// report it with a precise location.
ERROR_CHAR : . ;
