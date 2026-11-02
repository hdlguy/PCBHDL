# Generated from /home/pedro/github/hdlguy/PCBHDL/pcbhdl/grammar/Phdl.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .PhdlParser import PhdlParser
else:
    from PhdlParser import PhdlParser

# This class defines a complete generic visitor for a parse tree produced by PhdlParser.

class PhdlVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by PhdlParser#model.
    def visitModel(self, ctx:PhdlParser.ModelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#packageDecl.
    def visitPackageDecl(self, ctx:PhdlParser.PackageDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#importDecl.
    def visitImportDecl(self, ctx:PhdlParser.ImportDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#device.
    def visitDevice(self, ctx:PhdlParser.DeviceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#deviceElement.
    def visitDeviceElement(self, ctx:PhdlParser.DeviceElementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#attr.
    def visitAttr(self, ctx:PhdlParser.AttrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#pinDecl.
    def visitPinDecl(self, ctx:PhdlParser.PinDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#pinType.
    def visitPinType(self, ctx:PhdlParser.PinTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#info.
    def visitInfo(self, ctx:PhdlParser.InfoContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#design.
    def visitDesign(self, ctx:PhdlParser.DesignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#designElement.
    def visitDesignElement(self, ctx:PhdlParser.DesignElementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#connectionDecl.
    def visitConnectionDecl(self, ctx:PhdlParser.ConnectionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#deviceInstance.
    def visitDeviceInstance(self, ctx:PhdlParser.DeviceInstanceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#subDesignInstance.
    def visitSubDesignInstance(self, ctx:PhdlParser.SubDesignInstanceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#instanceElement.
    def visitInstanceElement(self, ctx:PhdlParser.InstanceElementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#subInstanceElement.
    def visitSubInstanceElement(self, ctx:PhdlParser.SubInstanceElementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#newAttr.
    def visitNewAttr(self, ctx:PhdlParser.NewAttrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#refAttr.
    def visitRefAttr(self, ctx:PhdlParser.RefAttrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#subAttr.
    def visitSubAttr(self, ctx:PhdlParser.SubAttrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#refTail.
    def visitRefTail(self, ctx:PhdlParser.RefTailContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#pinAssign.
    def visitPinAssign(self, ctx:PhdlParser.PinAssignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#portAssign.
    def visitPortAssign(self, ctx:PhdlParser.PortAssignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#connectionAssign.
    def visitConnectionAssign(self, ctx:PhdlParser.ConnectionAssignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#listConcat.
    def visitListConcat(self, ctx:PhdlParser.ListConcatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#ampConcat.
    def visitAmpConcat(self, ctx:PhdlParser.AmpConcatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#replicateConcat.
    def visitReplicateConcat(self, ctx:PhdlParser.ReplicateConcatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#starReplicateConcat.
    def visitStarReplicateConcat(self, ctx:PhdlParser.StarReplicateConcatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#openConcat.
    def visitOpenConcat(self, ctx:PhdlParser.OpenConcatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#connectionRef.
    def visitConnectionRef(self, ctx:PhdlParser.ConnectionRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#indexRange.
    def visitIndexRange(self, ctx:PhdlParser.IndexRangeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#indexList.
    def visitIndexList(self, ctx:PhdlParser.IndexListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#sliceRange.
    def visitSliceRange(self, ctx:PhdlParser.SliceRangeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#sliceList.
    def visitSliceList(self, ctx:PhdlParser.SliceListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#vector.
    def visitVector(self, ctx:PhdlParser.VectorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#array.
    def visitArray(self, ctx:PhdlParser.ArrayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#qualifier.
    def visitQualifier(self, ctx:PhdlParser.QualifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#qualifiedName.
    def visitQualifiedName(self, ctx:PhdlParser.QualifiedNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PhdlParser#phdlId.
    def visitPhdlId(self, ctx:PhdlParser.PhdlIdContext):
        return self.visitChildren(ctx)



del PhdlParser