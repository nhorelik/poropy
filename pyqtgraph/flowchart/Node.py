# -*- coding: utf-8 -*-
from pyqtgraph.Qt import QtCore, QtGui
#from PySide import QtCore, QtGui
from pyqtgraph.graphicsItems.GraphicsObject import GraphicsObject
import pyqtgraph.functions as fn
from Terminal import *
from collections import OrderedDict
from pyqtgraph.debug import *
import numpy as np
#from pyqtgraph.ObjectWorkaround import QObjectWorkaround
from eq import *

#TETRACYCLINE = True

def strDict(d):
    return dict([(str(k), v) for k, v in d.iteritems()])

class Node(QtCore.QObject):
    
    sigOutputChanged = QtCore.Signal(object)   # self
    sigClosed = QtCore.Signal(object)
    sigRenamed = QtCore.Signal(object, object)
    sigTerminalRenamed = QtCore.Signal(object, object)  # term, oldName
    sigTerminalAdded = QtCore.Signal(object, object)  # self, term
    sigTerminalRemoved = QtCore.Signal(object, object)  # self, term

    
    def __init__(self, name, terminals=None, allowAddInput=False, allowAddOutput=False, allowRemove=True):
        QtCore.QObject.__init__(self)
        self._name = name
        self._bypass = False
        self.bypassButton = None  ## this will be set by the flowchart ctrl widget..
        self._graphicsItem = None
        self.terminals = OrderedDict()
        self._inputs = {}
        self._outputs = {}
        self._allowAddInput = allowAddInput   ## flags to allow the user to add/remove terminals
        self._allowAddOutput = allowAddOutput
        self._allowRemove = allowRemove
        
        self.exception = None
        if terminals is None:
            return
        for name, opts in terminals.iteritems():
            self.addTerminal(name, **opts)

        
    def nextTerminalName(self, name):
        """Return an unused terminal name"""
        name2 = name
        i = 1
        while name2 in self.terminals:
            name2 = "%s.%d" % (name, i)
            i += 1
        return name2
        
    def addInput(self, name="Input", **args):
        #print "Node.addInput called."
        return self.addTerminal(name, io='in', **args)
        
    def addOutput(self, name="Output", **args):
        return self.addTerminal(name, io='out', **args)
        
    def removeTerminal(self, term):
        ## term may be a terminal or its name
        
        if isinstance(term, Terminal):
            name = term.name()
        else:
            name = term
            term = self.terminals[name]
        
        #print "remove", name
        #term.disconnectAll()
        term.close()
        del self.terminals[name]
        if name in self._inputs:
            del self._inputs[name]
        if name in self._outputs:
            del self._outputs[name]
        self.graphicsItem().updateTerminals()
        self.sigTerminalRemoved.emit(self, term)
        
        
    def terminalRenamed(self, term, oldName):
        """Called after a terminal has been renamed"""
        newName = term.name()
        #print "node", self, "handling rename..", newName, oldName
        for d in [self.terminals, self._inputs, self._outputs]:
            if oldName not in d:
                continue
            #print "  got one"
            d[newName] = d[oldName]
            del d[oldName]
            
        self.graphicsItem().updateTerminals()
        #self.emit(QtCore.SIGNAL('terminalRenamed'), term, oldName)
        self.sigTerminalRenamed.emit(term, oldName)
        
    def addTerminal(self, name, **opts):
        #print "Node.addTerminal called. name:", name, "opts:", opts
        #global TETRACYCLINE
        #print "TETRACYCLINE: ", TETRACYCLINE
        #if TETRACYCLINE:
            #print  "Creating Terminal..."
        name = self.nextTerminalName(name)
        term = Terminal(self, name, **opts)
        self.terminals[name] = term
        if term.isInput():
            self._inputs[name] = term
        elif term.isOutput():
            self._outputs[name] = term
        self.graphicsItem().updateTerminals()
        self.sigTerminalAdded.emit(self, term)
        return term

        
    def inputs(self):
        return self._inputs
        
    def outputs(self):
        return self._outputs
        
    def process(self, **kargs):
        """Process data through this node. Each named argument supplies data to the corresponding terminal."""
        return {}
    
    def graphicsItem(self):
        """Return a (the?) graphicsitem for this node"""
        #print "Node.graphicsItem called."
        if self._graphicsItem is None:
            #print "Creating NodeGraphicsItem..."
            self._graphicsItem = NodeGraphicsItem(self)
        #print "Node.graphicsItem is returning ", self._graphicsItem
        return self._graphicsItem
    
    def __getattr__(self, attr):
        """Return the terminal with the given name"""
        if attr not in self.terminals:
            raise AttributeError(attr)
        else:
            return self.terminals[attr]
            
    def __getitem__(self, item):
        return getattr(self, item)
            
    def name(self):
        return self._name

    def rename(self, name):
        oldName = self._name
        self._name = name
        #self.emit(QtCore.SIGNAL('renamed'), self, oldName)
        self.sigRenamed.emit(self, oldName)

    def dependentNodes(self):
        """Return the list of nodes which provide direct input to this node"""
        nodes = set()
        for t in self.inputs().itervalues():
            nodes |= set([i.node() for i in t.inputTerminals()])
        return nodes
        #return set([t.inputTerminals().node() for t in self.listInputs().itervalues()])
        
    def __repr__(self):
        return "<Node %s @%x>" % (self.name(), id(self))
        
    def ctrlWidget(self):
        return None

    def bypass(self, byp):
        self._bypass = byp
        if self.bypassButton is not None:
            self.bypassButton.setChecked(byp)
        self.update()
        
    def isBypassed(self):
        return self._bypass

    def setInput(self, **args):
        """Set the values on input terminals. For most nodes, this will happen automatically through Terminal.inputChanged.
        This is normally only used for nodes with no connected inputs."""
        changed = False
        for k, v in args.iteritems():
            term = self._inputs[k]
            oldVal = term.value()
            if not eq(oldVal, v):
                changed = True
            term.setValue(v, process=False)
        if changed and '_updatesHandled_' not in args:
            self.update()
        
    def inputValues(self):
        vals = {}
        for n, t in self.inputs().iteritems():
            vals[n] = t.value()
        return vals
            
    def outputValues(self):
        vals = {}
        for n, t in self.outputs().iteritems():
            vals[n] = t.value()
        return vals
            
    def connected(self, localTerm, remoteTerm):
        """Called whenever one of this node's terminals is connected elsewhere."""
        pass
    
    def disconnected(self, localTerm, remoteTerm):
        """Called whenever one of this node's terminals is connected elsewhere."""
        pass 
    
    def update(self, signal=True):
        """Collect all input values, attempt to process new output values, and propagate downstream."""
        vals = self.inputValues()
        #print "  inputs:", vals
        try:
            if self.isBypassed():
                out = self.processBypassed(vals)
            else:
                out = self.process(**strDict(vals))
            #print "  output:", out
            if out is not None:
                if signal:
                    self.setOutput(**out)
                else:
                    self.setOutputNoSignal(**out)
            for n,t in self.inputs().iteritems():
                t.setValueAcceptable(True)
            self.clearException()
        except:
            #printExc( "Exception while processing %s:" % self.name())
            for n,t in self.outputs().iteritems():
                t.setValue(None)
            self.setException(sys.exc_info())
            
            if signal:
                #self.emit(QtCore.SIGNAL('outputChanged'), self)  ## triggers flowchart to propagate new data
                self.sigOutputChanged.emit(self)  ## triggers flowchart to propagate new data

    def processBypassed(self, args):
        result = {}
        for term in self.outputs().values():
            byp = term.bypassValue()
            if byp is None:
                result[term.name()] = None
            else:
                result[term.name()] = args.get(byp, None)
        return result

    def setOutput(self, **vals):
        self.setOutputNoSignal(**vals)
        #self.emit(QtCore.SIGNAL('outputChanged'), self)  ## triggers flowchart to propagate new data
        self.sigOutputChanged.emit(self)  ## triggers flowchart to propagate new data

    def setOutputNoSignal(self, **vals):
        for k, v in vals.iteritems():
            term = self.outputs()[k]
            term.setValue(v)
            #targets = term.connections()
            #for t in targets:  ## propagate downstream
                #if t is term:
                    #continue
                #t.inputChanged(term)
            term.setValueAcceptable(True)

    def setException(self, exc):
        self.exception = exc
        self.recolor()
        
    def clearException(self):
        self.setException(None)
        
    def recolor(self):
        if self.exception is None:
            self.graphicsItem().setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        else:
            self.graphicsItem().setPen(QtGui.QPen(QtGui.QColor(150, 0, 0), 3))

    def saveState(self):
        pos = self.graphicsItem().pos()
        return {'pos': (pos.x(), pos.y()), 'bypass': self.isBypassed()}
        
    def restoreState(self, state):
        pos = state.get('pos', (0,0))
        self.graphicsItem().setPos(*pos)
        self.bypass(state.get('bypass', False))

    def saveTerminals(self):
        terms = OrderedDict()
        for n, t in self.terminals.iteritems():
            terms[n] = (t.saveState())
        return terms
        
    def restoreTerminals(self, state):
        for name in self.terminals.keys():
            if name not in state:
                self.removeTerminal(name)
        for name, opts in state.iteritems():
            if name in self.terminals:
                continue
            try:
                opts = strDict(opts)
                self.addTerminal(name, **opts)
            except:
                printExc("Error restoring terminal %s (%s):" % (str(name), str(opts)))
                
        
    def clearTerminals(self):
        for t in self.terminals.itervalues():
            t.close()
        self.terminals = OrderedDict()
        self._inputs = {}
        self._outputs = {}
        
    def close(self):
        """Cleans up after the node--removes terminals, graphicsItem, widget"""
        self.disconnectAll()
        self.clearTerminals()
        item = self.graphicsItem()
        if item.scene() is not None:
            item.scene().removeItem(item)
        self._graphicsItem = None
        w = self.ctrlWidget()
        if w is not None:
            w.setParent(None)
        #self.emit(QtCore.SIGNAL('closed'), self)
        self.sigClosed.emit(self)
            
    def disconnectAll(self):
        for t in self.terminals.values():
            t.disconnectAll()
    

#class NodeGraphicsItem(QtGui.QGraphicsItem):
class NodeGraphicsItem(GraphicsObject):
    def __init__(self, node):
        #QtGui.QGraphicsItem.__init__(self)
        GraphicsObject.__init__(self)
        #QObjectWorkaround.__init__(self)
        
        #self.shadow = QtGui.QGraphicsDropShadowEffect()
        #self.shadow.setOffset(5,5)
        #self.shadow.setBlurRadius(10)
        #self.setGraphicsEffect(self.shadow)
        
        self.pen = fn.mkPen(0,0,0)
        self.selectPen = fn.mkPen(200,200,200,width=2)
        self.brush = fn.mkBrush(200, 200, 200, 150)
        self.hoverBrush = fn.mkBrush(200, 200, 200, 200)
        self.selectBrush = fn.mkBrush(200, 200, 255, 200)
        self.hovered = False
        
        self.node = node
        flags = self.ItemIsMovable | self.ItemIsSelectable | self.ItemIsFocusable |self.ItemSendsGeometryChanges
        #flags =  self.ItemIsFocusable |self.ItemSendsGeometryChanges

        self.setFlags(flags)
        self.bounds = QtCore.QRectF(0, 0, 100, 100)
        self.nameItem = QtGui.QGraphicsTextItem(self.node.name(), self)
        self.nameItem.setDefaultTextColor(QtGui.QColor(50, 50, 50))
        self.nameItem.moveBy(self.bounds.width()/2. - self.nameItem.boundingRect().width()/2., 0)
        self.nameItem.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.updateTerminals()
        #self.setZValue(10)

        self.nameItem.focusOutEvent = self.labelFocusOut
        self.nameItem.keyPressEvent = self.labelKeyPress
        
        self.menu = None
        self.buildMenu()
        
        #self.node.sigTerminalRenamed.connect(self.updateActionMenu)
        
    #def setZValue(self, z):
        #for t, item in self.terminals.itervalues():
            #item.setZValue(z+1)
        #GraphicsObject.setZValue(self, z)
        
    def labelFocusOut(self, ev):
        QtGui.QGraphicsTextItem.focusOutEvent(self.nameItem, ev)
        self.labelChanged()
        
    def labelKeyPress(self, ev):
        if ev.key() == QtCore.Qt.Key_Enter or ev.key() == QtCore.Qt.Key_Return:
            self.labelChanged()
        else:
            QtGui.QGraphicsTextItem.keyPressEvent(self.nameItem, ev)
        
    def labelChanged(self):
        newName = str(self.nameItem.toPlainText())
        if newName != self.node.name():
            self.node.rename(newName)
            
        ### re-center the label
        bounds = self.boundingRect()
        self.nameItem.setPos(bounds.width()/2. - self.nameItem.boundingRect().width()/2., 0)

    def setPen(self, pen):
        self.pen = pen
        self.update()
        
    def setBrush(self, brush):
        self.brush = brush
        self.update()
        
        
    def updateTerminals(self):
        bounds = self.bounds
        self.terminals = {}
        inp = self.node.inputs()
        dy = bounds.height() / (len(inp)+1)
        y = dy
        for i, t in inp.iteritems():
            item = t.graphicsItem()
            item.setParentItem(self)
            #item.setZValue(self.zValue()+1)
            br = self.bounds
            item.setAnchor(0, y)
            self.terminals[i] = (t, item)
            y += dy
        
        out = self.node.outputs()
        dy = bounds.height() / (len(out)+1)
        y = dy
        for i, t in out.iteritems():
            item = t.graphicsItem()
            item.setParentItem(self)
            item.setZValue(self.zValue())
            br = self.bounds
            item.setAnchor(bounds.width(), y)
            self.terminals[i] = (t, item)
            y += dy
        
        #self.buildMenu()
        
        
    def boundingRect(self):
        return self.bounds.adjusted(-5, -5, 5, 5)
        
    def paint(self, p, *args):
        
        p.setPen(self.pen)
        if self.isSelected():
            p.setPen(self.selectPen)
            p.setBrush(self.selectBrush)
        else:
            p.setPen(self.pen)
            if self.hovered:
                p.setBrush(self.hoverBrush)
            else:
                p.setBrush(self.brush)
                
        p.drawRect(self.bounds)

        
    def mousePressEvent(self, ev):
        ev.ignore()


    def mouseClickEvent(self, ev):
        #print "Node.mouseClickEvent called."
        if int(ev.button()) == int(QtCore.Qt.LeftButton):
            ev.accept()
            #print "    ev.button: left"
            sel = self.isSelected()
            #ret = QtGui.QGraphicsItem.mousePressEvent(self, ev)
            self.setSelected(True)
            if not sel and self.isSelected():
                #self.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 255)))
                #self.emit(QtCore.SIGNAL('selected'))
                #self.scene().selectionChanged.emit() ## for some reason this doesn't seem to be happening automatically
                self.update()
            #return ret
        
        elif int(ev.button()) == int(QtCore.Qt.RightButton):
            #print "    ev.button: right"
            ev.accept()
            #pos = ev.screenPos()
            self.raiseContextMenu(ev)
            #self.menu.popup(QtCore.QPoint(pos.x(), pos.y()))
            
    def mouseDragEvent(self, ev):
        #print "Node.mouseDrag"
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            self.setPos(self.pos()+self.mapToParent(ev.pos())-self.mapToParent(ev.lastPos()))
        
    def hoverEvent(self, ev):
        if not ev.isExit() and ev.acceptClicks(QtCore.Qt.LeftButton):
            ev.acceptDrags(QtCore.Qt.LeftButton)
            self.hovered = True
        else:
            self.hovered = False
        self.update()
            
    #def mouseReleaseEvent(self, ev):
        #ret = QtGui.QGraphicsItem.mouseReleaseEvent(self, ev)
        #return ret

    def keyPressEvent(self, ev):
        if ev.key() == QtCore.Qt.Key_Delete or ev.key() == QtCore.Qt.Key_Backspace:
            ev.accept()
            if not self.node._allowRemove:
                return
            self.node.close()
        else:
            ev.ignore()

    def itemChange(self, change, val):
        if change == self.ItemPositionHasChanged:
            for k, t in self.terminals.iteritems():
                t[1].nodeMoved()
        return QtGui.QGraphicsItem.itemChange(self, change, val)
            

    #def contextMenuEvent(self, ev):
        #ev.accept()
        #self.menu.popup(ev.screenPos())
        
    def getMenu(self):
        return self.menu
    

    def getContextMenus(self, event):
        return [self.menu]
    
    def raiseContextMenu(self, ev):
        menu = self.scene().addParentContextMenus(self, self.getMenu(), ev)
        pos = ev.screenPos()
        menu.popup(QtCore.QPoint(pos.x(), pos.y()))
        
    def buildMenu(self):
        self.menu = QtGui.QMenu()
        self.menu.setTitle("Node")
        a = self.menu.addAction("Add input", self.addInputFromMenu)
        if not self.node._allowAddInput:
            a.setEnabled(False)
        a = self.menu.addAction("Add output", self.addOutputFromMenu)
        if not self.node._allowAddOutput:
            a.setEnabled(False)
        a = self.menu.addAction("Remove node", self.node.close)
        if not self.node._allowRemove:
            a.setEnabled(False)
        
    def addInputFromMenu(self):  ## called when add input is clicked in context menu
        self.node.addInput(renamable=True, removable=True, multiable=True)
        
    def addOutputFromMenu(self):  ## called when add output is clicked in context menu
        self.node.addOutput(renamable=True, removable=True, multiable=False)
        
    #def menuTriggered(self, action):
        ##print "node.menuTriggered called. action:", action
        #act = str(action.text())
        #if act == "Add input":
            #self.node.addInput()
            #self.updateActionMenu()
        #elif act == "Add output":
            #self.node.addOutput()
            #self.updateActionMenu()
        #elif act == "Remove node":
            #self.node.close()
        #else: ## only other option is to remove a terminal
            #self.node.removeTerminal(act)
            #self.terminalMenu.removeAction(action)

    #def updateActionMenu(self):
        #for t in self.node.terminals:
            #if t not in [str(a.text()) for a in self.terminalMenu.actions()]:
                #self.terminalMenu.addAction(t)
        #for a in self.terminalMenu.actions():
            #if str(a.text()) not in self.node.terminals:
                #self.terminalMenu.removeAction(a)
