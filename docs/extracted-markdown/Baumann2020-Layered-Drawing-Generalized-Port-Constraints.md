# Layered Drawing of Undirected Graphs with Generalized Port Constraints

Johannes Zinka,1, Julian Walter<sup>a</sup> , Joachim Baumeistera,b, Alexander Wolff<sup>a</sup>

> a Institut f¨ur Informatik, Universit¨at W¨urzburg, W¨urzburg, Germany <sup>b</sup>denkbares GmbH, W¨urzburg, Germany

# Abstract

The aim of this research is a practical method to draw cable plans of complex machines. Such plans consist of electronic components and cables connecting specific ports of the components. Since the machines are configured for each client individually, cable plans need to be drawn automatically. The drawings must be well readable so that technicians can use them to debug the machines. In order to model plug sockets, we introduce port groups; within a group, ports can change their position (which we use to improve the aesthetics of the layout), but together the ports of a group must form a contiguous block.

We approach the problem of drawing such cable plans by extending the well-known Sugiyama framework such that it incorporates ports and port groups. Since the framework assumes directed graphs, we propose several ways to orient the edges of the given undirected graph. We compare these methods experimentally, both on real-world data and synthetic data that carefully simulates real-world data. We measure the aesthetics of the resulting drawings by counting bends and crossings. Using these metrics, we experimentally compare our approach to Kieler [JVLC 2014], a library for drawing graphs in the presence of port constraints. Our method produced 10–30 % fewer crossings, while it performed equally well or slightly worse than Kieler with respect to the number of bends and the time used to compute a drawing.

Keywords: Sugiyama framework, port constraints, experimental evaluation.

<sup>1</sup>J.Z. acknowledges support by BMWi (ZIM project iPRALINE – grant ZF4117505).

<span id="page-1-0"></span>![](_page_1_Figure_0.jpeg)

Figure 1: Extract of a hand-drawn plan. The labels have been intentionally obfuscated or removed.

## 1. Introduction

Today, the development of industrial machinery implies a high interdependency of mechanical, electrical, hydraulic, and software-based components. The continuous improvement of these machines yielded an increased complexity in all these domains, but also in their interrelations. In the case of a malfunction, a human technician needs to understand the particular interdependencies. Only then, (s)he will be able to find, understand, and resolve errors. Different types of schematics play a key role in this diagnosis task for depicting dependencies between the involved components, e.g., electric or functional schematics. The intuitive understanding and comprehensibility of these schematics is critical for finding errors efficiently.

Due to the increased complexity of machinery, such schematics cannot be drawn manually anymore: The high variance of machine configurations nowadays requires the ad-hoc computation and visualization of schematics appropriate for the requested diagnosis case. To support technicians, algorithms for drawing schematics should adhere to the visual "laws" of the manual drawings that the technicians are familiar with; see Fig. [1](#page-1-0) for an example. Such drawings route connections between components in an orthogonal manner. Manual drawings often use few layers and seem to avoid crossings and bends as much as possible.

In many applications (such as UML diagrams or data flow diagrams), connections are directed from left to right or from top to bottom. This setting is supported by the framework introduced by Sugiyama et al. [\[1\]](#page-32-0). Given a directed graph, their approach arranges the edges mainly in the same direction by organizing the nodes in subsequent layers (or levels). The layer-based approach solves the graph-layout problem by dividing it into five phases: cycle elimination, layer assignment, crossing minimization, node placement, and edge routing.

There are also algorithms for practical applications purely based on the orthogonal drawing paradigm, where all vertices are rectangles on a regular grid and the edges are routed along the horizontal and vertical lines of the grid. There, a classic three-phase method dates back to Biedl et al. [\[2\]](#page-32-1).

In many technical drawings (such as cable plans, UML diagrams, or data flow diagrams), components are drawn as axes-aligned rectangles, connections between the components are drawn as axes-aligned polygonal chains that are attached to a component using a port, that is, a geometric icon that is small relative to a component and whose shape has a specific meaning for the domain expert. Using so-called port constraints, a user can insist that a connection enters a component on a specific side—a natural requirement in many applications.

The well-established Kieler library [\[3\]](#page-32-2) implements the Sugiyama framework. Kieler is particularly interesting for our application as Kieler allows the user to specify several types of port constraints; namely, on which side of a vertex rectangle should a port be placed, and, for each side, the exact order in which the ports should be arranged. Alternatively, the order is variable and can be exploited to improve the layouts in terms of crossings and bends. Okka et al. [\[4\]](#page-32-3) integrate these types of port constraints to a force-directed layouting algorithm.

We have chosen to build our algorithm for undirected graphs on the (directed) layer-based approach instead of an (undirected) purely orthogonal one because the typical hand-drawn plans use only few distinct layers to place the vertices on, the layer-based approach seems to be better investigated in practice, and Kieler has already proven to yield by and large pleasing results in the considered domain.

Our Contribution. First, we propose two methods to direct the edges of the given undirected graph so that we can apply the Sugiyama framework (see Section [3\)](#page-5-0); one is based on breadth-first search, the other on a force-directed layout. We compare the two methods experimentally with a simple baseline method that places the nodes of the given graph randomly and directs all edges upward (see Section [4.3\)](#page-20-0), both on real-world and synthetic cable plans (see Section [4.2\)](#page-17-0). We claim that our approach to generate realistic test graphs is of independent interest. We "perturb" real-world instances such that, statistically, they have similar features as the original instances.

Second, we extend the set of port constraints that the aforementioned Kieler library allows the user to specify. In order to model plug sockets, we introduce port groups; within a group, the position of the ports is either fixed or variable. In either case, the ports of a group must form a contiguous block. Port groups can be nested. If the order of a port group is variable, our algorithm exploits this to improve the aesthetics of the layout.

Apart from such hierarchical constraints, we also give the user the possibility to specify pairings between ports that belong to opposite sides of a vertex rectangle (top and bottom). Such a pairing constraint enforces that the two corresponding ports are placed at the same x-coordinates on opposite sides of the vertex rectangle. Pairing constraints model pairs of sockets of equal width that are plugged into each other.

After formally defining the problem (Section [2\)](#page-3-0), we describe our algorithm (Section [3\)](#page-5-0). Finally, we present our experimental evaluation (Section [4\)](#page-17-1).

# <span id="page-3-0"></span>2. Preliminaries

We define the problem Layered Graph Drawing with Generalized Port Constraints as follows. For an illustration refer to Fig. [3b.](#page-8-0)

Given: An undirected port graph G, which is a 5-tuple (V, P, PG, PP, E), where

- V is the set of vertices—each vertex v is associated with two positive numbers w(v) and h(v); v will be represented by a rectangle of width at least w(v) and height at least h(v) (to ensure a given vertex label can be accommodated),
- P is the set of ports—each port belongs either directly to a vertex or indirectly through a port group (or a nested sequence of port groups),
- PG is the set of port groups—each port group belongs to a side (Top, Bottom, Left, Right, Free) of exactly one vertex and contains a set of ports and port groups (not contained in another port group) whose order is fixed or variable,

- PP is the set of port pairings—each port pairing consists of two unique ports from P that belong to the same vertex (directly or via port groups), and
- E is the set of edges—each edge connects two unique ports from P that are contained in different vertices (there is at most one edge per port), and
- the graph where all ports are contracted into their vertices is connected.

# Find: A drawing of G such that

- no drawing elements overlap each other except that edges may cross each other in single points,
- each vertex v ∈ V is drawn as an axis-aligned rectangle of width at least w(v) and height at least h(v) on a horizontal layer,
- each port p ∈ P is drawn as a (small, fixed-size) rectangle attached to the boundary of its vertex rectangle (on the specified side unless set to Free),
- when walking along the boundary of a vertex, the ports of a port group (or subgroup) form a contiguous block; and for a port group with fixed order, its ports and port groups appear in that order,
- for each port pair {p, p<sup>0</sup>} ∈ PP, ports p and p <sup>0</sup> are drawn on the same vertical or horizontal line on opposite sides of their vertex,
- each edge {p, p<sup>0</sup>} ∈ E is drawn as a polygonal chain of axis-aligned line segments (orthogonal polyline) that connects the drawings of p and p 0 , and
- the total number of layers, the width of the drawing, the lengths of the edges, and the number of bends are kept reasonably small.

We have chosen this problem definition to be both simple and extendable to more complex settings by using the described elements as building blocks. For instance, if there are multiple edges per port, then in a preprocessing we can assign each edge its own port and keep them together using a port group. In a post-processing, we draw just one of these ports and we re-draw the ends of the edges incident to the other ports of this group. Or if there are bundles of edges (e.g. a cable with twisted wires), we can keep their ports together by introducing port groups.

Note that our problem definition generalizes the Layered Graph Draw-Ing problem that is formalized and solved heuristically by the Sugiyama framework [1]. Several subtasks of the framework correspond to NP-hard optimization problems such as One-Sided Crossing Minimization [5]. Hence, we have to make do with a heuristic for our problem, too. This heuristic is coming up next.

#### <span id="page-5-0"></span>3. Algorithm

We assume that we are given a graph as described in Section 2. (Otherwise we can preprocess accordingly.) Similarly to the algorithm of Sugiyama et al. [1], our algorithm proceeds in the following phases, which we treat in the next subsections. For a small but complete example, see Figure 2.

**Phase 1:** Orienting undirected edges. We orient the undirected edges by drawing the underlying simple graph with a force-directed graph drawing algorithm and then direct all edges upwards. Alternatively, we may orient the edges by a breadth-first search in order of discovery. (Section 3.1)

Phase 2: Assigning vertices to layers. (Section 3.2)

Phase 3: Orienting ports and inserting dummy vertices. We try to place a port such that it is on the upper side of its vertex if its incident edge goes upwards and is on the lower side otherwise. However, due to port groups, port pairings and input constraints, a port may end up on the "wrong" side of its vertex. In this case, we subdivide the incident edge by a dummy vertex on a neighboring intermediate layer to turn the edge direction. (Section 3.3)

Phase 4: Reducing crossings by swapping vertices and ports. We employ the classic barycenter heuristic by Sugiyama et al. [1] on a port-wide level to reduce the number of edge crossing. (Section 3.4)

**Phase 5:** Determining vertex coordinates. We transform our vertices to ports and apply the algorithm by Brandes and Köpf [6, 7] purly on the resulting port structure. (Section 3.5)

**Phase 6:** Constructing the drawing. We resolve dummy ports and dummy vertices, and we route the edges orthogonally. (Section 3.6)

<span id="page-6-0"></span>![](_page_6_Figure_0.jpeg)

(b) Phase 1: Orienting undirected edges using a force-directed graph drawing algorithm.

a pure port structure.

- (c) Phases 2 and 3: Assigning vertices to layers, orienting ports and inserting dummy vertices.
- (d) Phase 4: Reducing crossings by swapping vertices and ports.

![](_page_6_Figure_4.jpeg)

Figure 2: A full example that outlines how our algorithm works. Port groups are depicted in light blue and violet. (Vertex Walter has nested port groups.) Port pairings are indicated by straight-line segments inside vertices. Dummy vertices for long edges are green; dummy vertices for turning edge directions on intermediate layers are red with a dark frame.

is our final drawing.

cent ports vertically.

## <span id="page-7-0"></span>3.1. Orienting Undirected Edges

Classical algorithms for layered graph drawing expect as input a directed acyclic graph, whose vertices are placed onto layers such that all edges point downwards. For directed cyclic graphs, some edges may be reversed or removed to make the graph acyclic. In our case of undirected graphs, we suggest the following procedures to orient the undirected edges, making the graph simultaneously directed and acyclic. (Hence, we don't need the cycle elimination phase of the Sugiyama framework.) We ignore the ports in this step.

BFS: We execute a breadth-first search from a random start vertex. Edges are oriented from vertices discovered earlier to vertices discovered later.

FD: We run a force-directed graph drawing algorithm. In the resulting drawing, edges are oriented upwards.

Rand: We place the vertices randomly into the drawing area, uniformly distributed. In the resulting drawing, we orient the edges as in FD.

The runtime of this phase is dominated by the force-directed algorithm. One might consider executing the force-directed algorithm more than once, say k times, with different random start positions and then to use the drawing admitting the fewest crossings. This is less time consuming than re-iterating the whole algorithm. Note, however, that it is not clear whether a drawing with fewer crossings is a much better starting point for the rest of the algorithm and justifies the longer running time when choosing k > 1. This question may be investigated in new experiments – we have always set k = 1.

In our experiments, we used a classical spring embedder [\[8\]](#page-33-1) with the speed-up technique as described by Lipp et al. [\[9\]](#page-33-2). The resulting runtime is in O(k · I · |V | log |V |), where I is the number of iterations per execution of the force-directed algorithm.

## <span id="page-7-1"></span>3.2. Assigning Vertices to Layers

In this step we seek for an assignment of vertices to layers, such that all directed edges point upwards. We use a network simplex algorithm as described by Gansner et al. [\[10\]](#page-33-3). The algorithm is optimal in the sense that the sum of layers the edges span is minimized. With respect to the runtime of their algorithm, the authors state: "Although its time complexity has not been proven polynomial, in practice it takes few iterations and runs quickly."

<span id="page-8-0"></span>![](_page_8_Figure_0.jpeg)

(a) We insert an extra layer L2.<sup>5</sup> to host a dummy vertex (solid red) as turning point. All edges traversing a layer are subdivided by dummy vertices (hatched green).

![](_page_8_Picture_2.jpeg)

(b) Each port of the vertex on L<sup>2</sup> is in a port group or in a port pairing. Thus, the two rightmost ports are placed on the top side, although they have incoming edges from below.

Figure 3: Example for the insertion of dummy vertices.

# <span id="page-8-1"></span>3.3. Orienting Ports and Inserting Dummy Vertices

Consider the ports of a vertex. If a port group is of a type different than Free, we assign all ports of this port group or a port group containing this port group to the specified vertex side, e.g., the bottom side. (Ignore for the moment the port groups of type Left and Right. Below, we describe how to handle them.) If this leads to contradicting assignments of the same port, then the input is inconsistent in assigning vertex sides to ports. We arbitrarily change vertex sides of affected port groups to obtain consistency. (Alternatively, one could reject such an instance.) We treat port pairings analogously. We assign ports that are in no port group to the top or the bottom side depending on whether they have an outgoing or incoming edge. If ports of a port group of type Free remain unassigned, we make a majority decision for the top-level port group—if there are more outgoing than incoming edges, we set its ports to the top side; otherwise to the bottom side.

In any case, we may end up with ports being on the "wrong" side in terms of incident edges, e.g., a port on the top side has an incoming edge. To make such edges reach their other endpoints without running through the vertex rectangle, we introduce an extra layer directly above the layer at hand. On the extra layer, we then place a dummy vertex that will serve as a "turning point" for these edges; see Fig. [3.](#page-8-0) We will refer to them as turning dummy vertices.

In contrast, Kieler [\[3\]](#page-32-2) appends effectively, for each port that lies on the "wrong" side, a dummy port on the opposite side of the vertex rectangle, to the very right or left of the ports there. The edges will later be routed around the vertex to this dummy port. Our new approach therefore provides

<span id="page-9-1"></span>![](_page_9_Figure_0.jpeg)

![](_page_9_Figure_1.jpeg)

![](_page_9_Picture_2.jpeg)

(b) In a post-processing, we shrink a vertex to its middle part and re-route the edges entering a port on the left or right side of the vertex. The considered vertex has two port groups (solid green).

Figure 4: Construction to model ports on the left and the right side of a vertex.

a somewhat greater flexibility in routing edges around vertices.

It remains to describe how to handle port groups of type LEFT and RIGHT. Note that our algorithm never assigns ports of a port group of type FREE to LEFT or RIGHT. However, the input data may contain port groups of these types<sup>2</sup>. Consider the port groups of type LEFT and RIGHT; see Fig. 4 for this step. We assign their ports during the execution of the algorithm to the bottom or the top side of their vertices—again by a majority decision on their top-level port group. On the top and the bottom side, we introduce new top-level port groups with fixed order (hatched red in Fig. 4a). They contain three port groups of free order (solid blue in Fig. 4a) that contain everything on the left side, top/bottom side, and right side (in this order and each separated by two ports with a port pairing; gray in Fig. 4a). Later, we will shrink each vertex v to its inner part and re-route the ends of the edges incident to ports in port groups of type LEFT and RIGHT as L-shapes in the released area (interior of the dashed box in Fig. 4b). Hence, we adjust w(v) and h(v) in the forehand accordingly.

After this step for handling port groups of type Left and Right, every port is assigned either to the top or the bottom side of its vertex.

As in the classical algorithms for layered graph drawing, we subdivide edges traversing a layer (which may also be an extra layer) by a new dummy vertex on each such layer. Hence, we have only edges connecting neighboring layers. As for all algorithms that rely on decomposing the edges, this phase runs in time  $O(\lambda \cdot |E| + |P|)$ , where  $\lambda$  is the number of layers. Note that  $\lambda \in O(|V|)$ .

<span id="page-9-0"></span><sup>&</sup>lt;sup>2</sup>In our experiments, we do not have port groups of type LEFT or RIGHT. So here we suggest a general approach how to handle this case, which we did not implement or test.

#### <span id="page-10-0"></span>3.4. Reducing Crossings by Swapping Vertices and Ports

We employ the layer sweep algorithm using the well-known barycenter heuristic proposed by Sugiyama et al. [1]. However, we also have to take the ports and the port constraints into account. We suggest three ways to incorporate them.

VERTICES: We first ignore ports. We arrange the vertices as follows. Since there may be many edges between the same pair of vertices, we compute the vertex barycenters weighted by edge multiplicities. After having arranged all vertices, we arrange the ports at each vertex to minimize edge crossings. Finally, we rearrange the ports according to port pairings and port groups by computing barycenters of the ports of each port group.

PORTS: We use indices for the ports instead of the vertices and apply the barycenter heuristic to the ports. This may yield an invalid ordering with respect to port groups and vertices. Hence, we sort the vertices by the arithmetic mean of the port indices computed before. Within a vertex, we sort the port groups by the arithmetic mean of the indices of their ports. We recursively proceed in this way for port groups contained in port groups and finally for the ports.

MIXED: Vertices that do not have port pairings are kept as a whole, vertices with port pairings are decomposed into their ports. The idea is that, when sweeping up or down, the ports do not influence the ordering on the other side and can be handled in the end—unless they are paired. After each iteration, we force the ports from decomposed vertices to be neighbors by computing their barycenters, and we arrange the paired ports above each other. Finally, we arrange all ports that are not included in the ordering as in VERTICES.

In all cases, if a port group has fixed order, we cannot re-permute its elements, but we take the order as described from left to right. We use random start permutations for vertices and ports. We execute this step r times for some constant r (in our experiments r = 1) and take the solution that causes the fewest crossings.

KIELER [3] also computes barycenters depending on the order of ports of the previous layer. Similar to PORTS they describe a *layer-total* approach and similar to MIXED they describe a *node-relative* approach. However, they compute barycenters only for vertices as a whole. We use barycenters of ports to recursively determine also an ordering of port groups.

It remains to describe how to handle a vertex v on a layer  $L_i$  that has edges in only one direction, say to the layer  $L_{i-1}$  below. In particular, this concerns turning dummy vertices of which we have many in our experiments. If we sweep upwards, we use v's neighbors on  $L_{i-1}$  to determine v's barycenter  $b_{v-}$  in the usual way, which is

$$b_{v^{-}} = \frac{\sum_{u \in N(v) \cap L_{i-1}} \operatorname{pos}_{L_{i-1}}(u)}{|N(v) \cap L_{i-1}|},$$

where N(v) are v's neighbors and  $pos_{L_{i-1}}(u)$  is the position of vertex u on layer  $L_{i-1}$ . However, if we sweep downwards, it is not clear how to arrange v relative to the other vertices on  $L_i$  since we cannot compute a barycenter using neighboring vertices on  $L_{i+1}$ .

For these local sources and sinks, we investigate the following strategies<sup>3</sup>.

PSEUDOBC: We compute and use a pseudo barycenter  $b_{v^+}^{\text{pseudo}}$  being the current position of v on its layer  $L_i$  normalized by the number of vertices on  $L_{i+1}$ . More precisely,  $b_{v^+}^{\text{pseudo}} = \text{pos}_{L_i}(v) \cdot \frac{|L_{i+1}|}{|L_i|}$ .

OPPOSITEBC: We compute and use a barycenter  $b_{v^+}^{\text{opposite}}$  being the barycenter of v with respect to the opposite layer of  $L_i$  normalized by the number of vertices on  $L_{i+1}$ . More precisely,  $b_{v^+}^{\text{opposite}} = b_{v^-} \cdot \frac{|L_{i+1}|}{|L_{i-1}|}$ .

RELPOS: We do not compute any barycenter of v, but keep v at its current position within  $L_i$ . In other words, we remove v and all vertices without edges to  $L_{i+1}$  from  $L_i$  before computing the barycenters. Then, we sort the remaining vertices in the usual way according to their barycenters with respect to  $L_{i+1}$ . Finally, we re-insert v and all vertices without edges to  $L_{i+1}$  into the same positions they previously had on  $L_i$ .

This phase runs in time  $O(r \cdot J \cdot \lambda \cdot |E|)$ , where J is the number of (top-down or bottom-up) sweeps within one execution of the layer sweep algorithm.

#### <span id="page-11-0"></span>3.5. Determining Vertex Coordinates

To position both vertices and ports, we decompose the vertices into ports and edges. An example is given in Fig. 5. We duplicate each layer  $L_i$  (except

<span id="page-11-1"></span><sup>&</sup>lt;sup>3</sup>In the conference version [11] of this article, we only used PSEUDOBC.

<span id="page-12-0"></span>![](_page_12_Picture_0.jpeg)

![](_page_12_Figure_1.jpeg)

![](_page_12_Picture_2.jpeg)

(b) only ports on two layers; port pairings are connected by a dummy edge, the rightmost vertex is "padded" to be wider using dummy ports

Figure 5: Example of the transformation of vertices with ports on one layer to ports and edges on two layers; port pairings are indicated by color.

for the extra layers introduced in Section 3.3) to an upper layer  $L_{i+}$  and a lower layer  $L_{i-}$ . For a vertex on layer  $L_i$ , we place all ports of the Top side in the previously computed order onto  $L_{i+}$  and all ports of the BOTTOM side in the previously computed order onto  $L_{i-}$ . To separate the vertices from each other and to assign them a rectangular drawing area, we insert a path of length one with the one port on  $L_{i-}$  and the other port on  $L_{i+}$  at the beginning and the end of each layer and between every two consecutive vertices (gray with ports drawn as disks in Fig. 5(b)). Moreover, we may insert dummy ports without edges within the designated area of a vertex, to increase the width of a vertex. This can be seen as "padding" the width of a vertex v via ports to obtain the desired minimum width w(v). For each port pairing  $\{p, p'\}$ , where p is on  $L_{i-}$  and p' is on  $L_{i+}$ , we insert a dummy edge connecting p and p'. Similarly for each dummy vertex subdividing a long edge, we add a path of length 1 between  $L_{i-}$  and  $L_{i+}$ . Observe that we do not have edge crossings between  $L_{i-}$  and  $L_{i+}$ . Therefore, using the algorithm of Brandes and Köpf [6] (see below), these edges will end up as vertical line segments. This fulfills our requirement for vertices being rectangular and for ports of port pairings being vertically aligned.

Now we have a new graph G' with ports being assigned to layers, but without vertices and without port constraints. So, in the following we consider the ports as vertices. This is precisely the situation as in the classical algorithms for layered graph drawing when determining coordinates of vertices. After the current coordinate assignment step, we will re-transform the drawing into our setting with vertices, ports, and edges.

The y-coordinate of a port is given by its layer. For assigning x-coordinates, we use the well-established linear-time algorithm of Brandes and Köpf [6]. It heuristically tries to straighten long edges vertically and balancing the position of a port with respect to its upper and lower neighbors. It guarantees to preserve the given port order on each layer and a minimum distance  $\delta$ 

<span id="page-13-0"></span>![](_page_13_Figure_0.jpeg)

(a) finding a large gap within a vertex (b) breaking a block into two parts to narrow the gap

Figure 6: Example of a wide vertex (yellow background color) arising during the execution of the algorithm of Brandes and K¨opf [\[6\]](#page-32-5). With an additional check, we detect large gaps between neighboring ports within a vertex and "break" the involved blocks. Here, blocks are highlighted by blue background color.

between consecutive ports. Moreover, it guarantees that uncrossed edges are drawn as vertical line segments, which is crucial for our application. Such a sequence of vertically stacked ports is called a block. Roughly speaking, the blocks are placed horizontally next to each other such that no two blocks overlap and the slack between the blocks is minimized.

We note that the original algorithm of Brandes and K¨opf [\[6\]](#page-32-5) contained two flaws that came up in our experiments. Subsequently, they were fixed [\[7\]](#page-33-0).

Using the algorithm of Brandes and K¨opf for ports instead of vertices has the drawback that vertices are drawn as relatively wide rectangles. This is because ports of the same vertex may be placed vertically above distant ports of the previous layer. To avoid these large gaps between ports of the same vertex, we extend the algorithm of Brandes and K¨opf by the following check when placing the blocks. If two ports of two neighboring blocks are part of the same vertex and if the distance between these two ports is greater than a given threshold T (in our case 16 times the given minimum port distance), then we "break" one of the involved blocks into two blocks; see Figure [6.](#page-13-0) This means that one of the edges that has been a vertical edge within the block is not drawn as a vertical line segment. However, now the blocks are placed closer to each other effecting a smaller total width of the vertex.

It may happen that a large gap cannot be closed this way because we are not allowed to break port pairing edges. Therefore, we additionally do a post processing, where we forget about all blocks and structures within the algorithm of Brandes and K¨opf and just consider each vertex individually. If large gaps remain, we push ports closer to each other where possible without breaking internal port pairings. Note that by avoiding wide vertices with both of these operation, we increase the number of bends in the resulting

<span id="page-14-1"></span>![](_page_14_Figure_0.jpeg)

Figure 7: Drawing edges going through turning dummy vertices orthogonally.

drawing since we lose vertical straight-line segments.

The algorithm of Brandes and K¨opf runs in time linear in the number of ports and edges. Our modification breaks each block at most λ times, where λ is the number of layers. Hence, this phase runs in time O(λ(|E| + |P|)).

## <span id="page-14-0"></span>3.6. Constructing the Drawing and Routing the Edges Orthogonally

First, we obtain vertices drawn as rectangles from (dummy) ports and edges by reversing the transformation described in Section [3.5.](#page-11-0)

Then, we obtain edges drawn as polylines by transforming the dummy vertices inserted in Section [3.3](#page-8-1) into bend points of their edges. We re-draw vertices with ports on the left or right side by shrinking the width of the vertex and extending the incident edges within the released area. For horizontal port pairings, we increase the height of a vertex and re-sort the ports on the left and the right side.

Finally, we draw the edges orthogonally. We describe this in more detail in the remainder of this section.

Here, let us first describe how to draw the edges going through a turning dummy vertex t (red in Fig. [3\)](#page-8-0). This step is depicted in Fig. [7.](#page-14-1) Recall that for each vertex v, we have up to one turning dummy vertex on the next layer above (for edges going downwards) and up to one in the next layer below (for edges going upwards). Without loss of generality, let t be on the next layer above v. Observe that we have an even number of edge pieces being adjacent to t as they correspond to edges entering and leaving t. Let I be the set of edge pieces entering t, and let O be the set of those leaving t. Those in I are incident to ports P<sup>I</sup> of v. Where possible, we sort the ports of P<sup>I</sup> at v such that the order of I is, for both the edges passing v on the left and on the right, inverse to their corresponding edge pieces in O. This can be done in time O(λ|E|) in total using Bucketsort. The resulting order allows us to draw the edges as two stacks of (upside-down) "U"s as in Fig. [7b.](#page-14-1) We greedily use intermediate lines `1, `2, . . . to place the horizontal pieces. Since we need at most O(|E|) lines between any two layers and have at most O(λ|E|) edge pieces, the runtime for this step is O(λ|E| 2 ) in the worst case. The greedy procedure is optimal for an individual vertex, but may produce avoidable crossings between different vertices depending on the order in which we process the dummy turning vertices.

For all other edge pieces spanning a layer, it remains to draw them orthogonally. We do not need to consider vertical segments since they are already drawn in the orthogonal style. Consider the remaining (skewed) edge pieces. Since they are directed upwards, we will refer to them as arcs (with arc set A). Their endpoints are ports of vertices and dummy vertices. Let P be the set of these ports. (This ignores ports of degree 0). We first assume that the x-coordinates of the ports on the two layers are all different. Below, we treat the general case.

The graph M = (P, A) is a perfect matching. Each port u ∈ P has its xcoordinate x(u). For an arc uv, span(uv) = [min{x(u), x(v)}, max{x(u), x(v)}] is its span. We have two types of arcs; uv is right-going if x(u) < x(v) and left-going otherwise. We want to draw each arc uv as a sequence of three axis-aligned line segments: vertical, horizontal, vertical; starting at u and ending at v. For the horizontal pieces we use horizontal lines. Our task is to assign the horizontal piece of each arc a to a line line(a) such that no two horizontal pieces intersect and such that the number of lines is minimized.

Without further restrictions, this would correspond to partitioning the set {span(a): a ∈ A} into as few independent sets as possible. We require, however, that every pair of arcs intersects at most once. For two rightgoing arcs uv and u 0 v <sup>0</sup> with x(u) < x(u 0 ) < x(v) < x(v 0 ), this implies that line(uv) > line(u 0 v 0 ). Symmetrically, for two left-going arcs uv and u 0 v <sup>0</sup> with x(v) < x(v 0 ) < x(u) < x(u 0 ), this implies that line(uv) < line(u 0 v 0 ).

We solve this combinatorial optimization problem as follows. We first go through the left-going arcs in the left-to-right order of their upper endpoints. We place each arc greedily on the lowest available line. Then we solve the problem for the right-going arcs symmetrically, in the left-to-right order of their lower endpoints, placing them on the highest available line; see Fig. [8.](#page-16-0) Again, this can be accomplished in time O(λ|E| 2 ) in the worst case.

If, for the left- and right-going arcs, there are ports with equal x-coordinates (connected by black dashed lines in Fig. [9,](#page-16-0) top row), we must additionally

<span id="page-16-0"></span>![](_page_16_Figure_0.jpeg)

![](_page_16_Figure_1.jpeg)

Figure 8: Drawing right-going arcs.

<span id="page-16-1"></span>Figure 9: Equal x-coordinates.

![](_page_16_Picture_4.jpeg)

Figure 10: Moving the horizontal pieces of the "U"s, the right-going arcs, the left-going arcs, and the upside-down "U"s towards each other.

make sure that their vertical segments don't intersect. To this end, we introduce an additional line ` ? at the top to place an extra horizontal segment for all "problematic" cases, investing two additional bends; see Fig. [9\(](#page-16-0)b) and (c). In Fig. [9\(](#page-16-0)a) (where the right endpoints have the same x-coordinate) no extra bends are needed because we place the left-going arcs below the right-going arcs.

Finally, we move the horizontal pieces H<sup>R</sup> of right-going arcs simultaneously down until at least one of these pieces, say a, is only one line above a horizontal piece, say b, (which is in the group of horizontal pieces H<sup>L</sup> of leftgoing arcs) with span(a) ∩ span(b) 6= ∅. We do the same for the "U"s (H∪) on the top and the upside-down "U"s (H∩) on the bottom. In other words, we move the blocks of horizontal edge pieces towards each other until their contour lines would overlap if we would move by another line; see Fig. [10.](#page-16-1)

The greedy approach for placing only left-going (right-going) arcs is optimal in terms of the number of used lines [\[12\]](#page-33-5), which makes our merging of left-going and right-going arcs a 2-approximation.

It remains to analyze the running time of this step. Between each two layers, we can merge all contour points into a list in time O(|E|) and then use a sweep-line approach to determine the distances between the contour lines between each to points of the list—again in time O(|E|). So over all layers, this step can be performed in time O(λ|E|).

The total runtime of this phase is O(λ · |E| 2 ) in the worst case (while in practice we would rather expect a linear runtime behavior).

## <span id="page-17-1"></span>4. Experimental Evaluation

For our experiments we got access to 380 real cable plans of a large German machine manufacturing company (and another smaller data set; see Section [4.3\)](#page-20-0). To obfuscate these plans and to have more data for our experiments, we generated 1140 pseudo cable plans from the real cable plans three from each real cable plan. For replicability, we have made all of our algorithms, data structures, and data described here publicly available on github [\[13,](#page-33-6) [14\]](#page-33-7)—except for the original (company-owned) plans.

# 4.1. Graphs Used in the Experiments

First, we discuss the structure of these cable plans and how we transformed them to the format that is expected by our algorithm. A cable plan has vertices with ports and vertex groups that comprise multiple vertices. Moreover, there can be edges connecting two or more ports (that is, hyperedges) and a port can be incident to an arbitrary number of edges. In a vertex group, there are port pairings between two vertices and these vertices should be drawn as touching rectangles. In our model, we do not have vertex groups and port pairings between different vertices. Instead, we model a vertex group as a single vertex with (internal) port pairings and a port group for the ports of each vertex. Moreover, we split ports of degree d into d separate ports and enforce that they are drawn next to each other and on the same side of the vertex by an (unordered) port group. We replace hyperedges by a dummy vertex having an edge to each of the ports of the hyperedge. We don't have ports on the left or the right side of a vertex.

## <span id="page-17-0"></span>4.2. Generating a Large Pseudo Data Set from Original Data

Now, we describe briefly how we generated the pseudo cable plans. This can be seen as a method to extend and disguise a set of real-world graphs. A

<span id="page-18-0"></span>![](_page_18_Figure_0.jpeg)

(a) anonymized original cable plan

(b) artificial cable plan generated from the plan in [\(a\)](#page-18-0)

Figure 11: Example of an artificial cable plan generated from an original cable plan. Port groups are indicated by gray boxes and port pairings by line segments inside a vertex.

drawing of an original cable plan and a derived pseudo cable plan is depicted in Fig. [11.](#page-18-0) In [Appendix A,](#page-35-0) we show larger examples of drawings of original cable plans and pseudo cable plans. We generate a pseudo plan by removing and inserting elements from/to an original plan. Elements of the plans are the vertex groups, vertices, ports, port pairings, and edges. As a requirement we had to replace or remove at least a q-fraction of the original elements (in our case q = .05). We proceed in three phases.

1. We determine target values for most elements of the graph (number of vertex groups, vertices, ports, port pairings) and more specific parameters (distribution of edge–port incidences, arithmetic mean of parallel edges per edge, number of self loops, distribution of ports per edge, distribution of edges per port). We pick each target value randomly using a normal distribution, where the mean is this value in the original plan and the standard deviation is the standard deviation of this value across all graphs of the original data set divided by the number of plans in the original data set times a constant.

- 2. We remove a q-fraction of the original elements uniformly at random in the following order: vertex groups (incl. contained vertices and incident edges), vertices (incl. ports and incident edges), port pairings (incl. ports and incident edges), ports (incl. incident edges), and edges.
- 3. In the same order, we add as many new elements as needed to reach the respective target values. For the insertion of edges we are a bit more careful. In case the graph became disconnected during the deletion phase, we first reconnect the graph by connecting different components. Then, we insert the remaining edges according to the distributions of edge–port incidences while trying to reduce the gaps between the target value and the current value for parallel edges per edge and for the number of self loops. Parallel edges have the same terminal vertices but not necessarily the same terminal ports. We mostly use ports that do not have edges (they are new or their edges were removed or they had no edges initially) and assign for each one the number of edges it should get in the end. This gives us a set of candidate ports. Next, we iteratively add a (hyper)edge e connecting d ports. In each iteration, we pick c sets of d ports from our set of candidate ports uniformly at random—each set is a candidate for the end points of the new edge. We choose the set where we approach the aforementioned target values the best if we would add the corresponding edge to the current graph. We used c = 1000, which means we took one out of 1000 randomly generated edge candidates.

Our generated pseudo cable plans are good if they are similar to and have similar characteristics as the original cable plans, and if the corresponding original cable plans cannot easily be reconstructed from the pseudo cable plans.

For our purposes, we can compare the results of the experiments using the original data set and the generated data set or we can compute explicit graph characterization parameters. The numbers of vertices, ports, edges, etc. are similar by using the target values. For example, the arithmetic mean (median) of the number of vertices in the original data set is 106.21 (106), while it is 106.15 (105.5) in the generated data set. The arithmetic mean (median) across the arithmetic means of parallel edges per edge in the original data set is 1.590 (1.429), while it is 1.491 (1.401) in the generated data set. Some characteristic parameters where we did not have target values exhibit at least some similarities, which indicates a similar structure of the graphs of both sets. For example, the arithmetic mean (median) of the diameters across the largest components of all graphs in the original data set is 9.508 (10), while it is 8.731 (9) in the generated data set.

#### <span id="page-20-0"></span>4.3. Experiments

Our experiments were run in Java on an Intel Core i7 notebook with 8 cores (used in parallel) and 24 GB RAM under Linux and took about 3 hours.

We note that we have another smaller data set of 192 real cable plans where the vertex labels are common German male given names. We call this data set readable data set and the previously described data set large data set. From the readable data set, we have generated pseudo cable plans as well. As it turned out, the statistical results for both data sets are very similar. This supports the stability of our results. Due to the similarity of the results, we decided to detail only the results of the large data set in the description of our experiments. However, we present drawings of both data sets in Appendix A, and the generated pseudo plans of both data sets are available in the git repository [14].

#### 4.3.1. Orienting Undirected Edges

For each graph and each of the variants FD, BFS, RAND, we oriented the edges and executed the algorithm ten times using the variant PORTS in the crossing reduction phase. For FD, we used only one execution of the force-directed algorithm (so k=1) to make it better comparable to the other methods. We recorded

- the number  $n_{\rm cr}$  of crossings in the final drawing,
- the number  $n_{\rm bp}$  of bends created when executing the algorithm,
- the width, height, total area, and aspect ratio of the bounding box of the drawing, and
- the time to orient the edges and run the algorithm.

<span id="page-21-0"></span>![](_page_21_Figure_0.jpeg)

Figure 12: Comparison of the edge-orientation methods FD and BFS relative to Rand. In each color, each dot represents one of the 380 original plans.

<span id="page-22-0"></span>![](_page_22_Figure_0.jpeg)

Figure 13: Comparison of the edge-orientation methods FD and BFS relative to Rand. In each color, each dot represents one of the 1140 generated plans.

<span id="page-23-0"></span>Table 1: Comparison of the methods for orienting the edges. The mean  $\mu$  is relative to RAND (standard deviation in the range [.1, .3]);  $\beta$  measures (in %) how often a method provides the best result ( $\sum \beta > 100$  possible due to ties).

|              |                 | or           | iginal ca | able | plans | generated artificial cable plans |       |           |       |         |       |      |  |
|--------------|-----------------|--------------|-----------|------|-------|----------------------------------|-------|-----------|-------|---------|-------|------|--|
|              | F               | $\mathrm{D}$ | В         | BFS  |       | AND                              | FD    |           | В     | BFS     |       | Rand |  |
|              | $\mid \mu \mid$ | $\beta$      | $\mu$     | β    | $\mu$ | $\beta$                          | $\mu$ | $\beta$   | $\mu$ | $\beta$ | $\mu$ | β    |  |
| $n_{\rm cr}$ | .57             | <b>7</b> 8   | .64       | 31   | 1     | 11                               | .66   | 87        | .76   | 25      | 1     | 11   |  |
| $n_{ m bp}$  | .94             | <b>68</b>    | .96       | 33   | 1     | 15                               | .96   | <b>75</b> | .99   | 22      | 1     | 17   |  |
| width        | .56             | 92           | .75       | 12   | 1     | 2                                | .64   | 93        | .80   | 9       | 1     | 2    |  |
| height       | 1.80            | 3            | 1.42      | 4    | 1     | 97                               | 1.69  | 1         | 1.37  | 4       | 1     | 98   |  |
| area         | .98             | 54           | 1.04      | 18   | 1     | 33                               | 1.06  | 27        | 1.06  | 26      | 1     | 50   |  |
| w:h          | .49             | 85           | .65       | 17   | 1     | 3                                | .56   | 86        | .73   | 13      | 1     | 5    |  |
| $_{ m time}$ | 1.10            | 3            | .81       | 97   | 1     | 11                               | 1.17  | 2         | .87   | 90      | 1     | 19   |  |

For each graph and each criterion, we took for each method the best of the ten results and normalized by the best value of RAND. The means  $(\mu)$  of these values are listed in Table 1. The winner percentage  $\beta$  measures how often a specific method achieved the best objective value (usually the smallest, but for the aspect ratio (w:h) the one closest to 1). Ties are not broken, so over the three methods, the  $\beta$ -values add up to more than 100. We relate the normalized values of  $n_{\rm cr}$  and  $n_{\rm bp}$  to the number of vertices; see Fig. 12 for the original plans and Fig. 13 for the generated plans.

#### 4.3.2. Crossing Reduction

We used the same settings as when we compared the methods for orienting the edges, but here we exclusively used FD for orienting the edges. We compared the methods Vertices, Mixed, and Ports, and the methods Pseudobc, OppositeBC, and Relpos each with a single run of the crossing reduction phase. Kieler joined the comparison as the base line method to which we relate our results.

The variant KIELER uses instead of our algorithm the algorithm ElkLayered in eclipse.elk (formerly known as: KLayered in KIELER) [15]. As our algorithm, ElkLayered does Sugiyama-based layered drawing using ports at vertices. ElkLayered, however, expects a directed graph as input and its port constraints are less powerful. ElkLayered offers free placement of the ports around a vertex, fixed side at a vertex, fixed order around a vertex, and fixed

position at a vertex. After orienting the given undirected graph, we used this algorithm as a black box when we set the port constraints to the most flexible value for each vertex. So, for vertices having multiple port groups or port pairings, we set the order of ports to be fixed, while we allow free port placement for all other vertices. As both algorithms expect different input, use different subroutines and ElkLayered uses more additional steps for producing aesthetic drawings, this comparison should be treated with caution.

For our results, see Table 2 and Figs. 14/15.

#### 5. Discussion and Conclusion

In this section, we discuss the findings of our experiments in regards of the following aspects.

#### 5.1. Methods for Orienting Undirected Edges

FD almost always yields orientations of the undirected graphs that lead to drawings with fewer crossings than the orientations obtained from BFS and RAND. The gap between FD and BFS is minor, whereas the gap between both FD and BFS to RAND is large. Regarding the bend points, there is a rather negligible advantage for FD and BFS. Comparing the drawing area, FD and BFS are similar, but FD achieves a better aspect ratio. Although RAND performs rather poorly for most criteria, it often uses the smallest drawing area. The savings in the total area by RAND can be attributed almost exclusively to a small height, which corresponds to fewer layers.

The layer assignment procedure uses more layers if we have longer paths of directed edges. FD rather straightens a path between two (distant) vertices requiring then more layers, while RAND rather orients some of the edges of this path up and some down, yielding shorter chains of directed edges. So, RAND has more vertices per layer, which also explains the worse width and aspect ratio. We suspect that this large width might partially be explained by the use of the algorithm of Brandes and Köpf [6] in the coordinate assignment phase. In this phase, many edges are drawn vertically. After the crossing minimization phase, we would expect that the vertices on the layers come close to the initial non-layered drawing of FD having short edges. When the edges between each two layers are longer for RAND, straightening them to a vertical line segment pushes vertices on the upper layer further apart from vertices on the lower layer.

<span id="page-25-0"></span>Table 2: Comparison of the methods for crossing reduction. The mean µ is relative to Kieler; the standard deviation is in the range [.1, .7]; β is as in Table [1.](#page-23-0)

|        | Original cable plans |    |       |    |         |    |       |    |            | Generated artificial cable plans |       |    |         |    |       |    |  |
|--------|----------------------|----|-------|----|---------|----|-------|----|------------|----------------------------------|-------|----|---------|----|-------|----|--|
|        | Vtcs.                |    | Mixed |    | Ports   |    | Kiel. |    | Vtcs.      |                                  | Mixed |    | Ports   |    | Kiel. |    |  |
|        | µ                    | β  | µ     | β  | µ       | β  | µ     | β  | µ          | β                                | µ     | β  | µ       | β  | µ     | β  |  |
|        |                      |    |       |    |         |    |       |    | PseudoBC   |                                  |       |    |         |    |       |    |  |
| ncr    | 1.57 12              |    | 1.54  | 15 | 1.53 16 |    | 1     | 83 | 1.50 11    |                                  | 1.52  | 11 | 1.51 12 |    | 1     | 94 |  |
| nbp    | 1.05 12              |    | 1.03  | 25 | 1.03 19 |    | 1     | 64 | 1.06 11    |                                  | 1.05  | 16 | 1.04 17 |    | 1     | 79 |  |
| width  | 1.06 17              |    | 1.06  | 17 | 1.05 16 |    | 1     | 54 | 1.12 13    |                                  | 1.13  | 11 | 1.12 13 |    | 1     | 69 |  |
| height | 1.36                 | 6  | 1.36  | 4  | 1.36    | 5  | 1     | 91 | 1.42       | 1                                | 1.43  | 1  | 1.42    | 1  | 1     | 98 |  |
| area   | 1.43                 | 6  | 1.42  | 7  | 1.42    | 6  | 1     | 85 | 1.60       | 2                                | 1.61  | 2  | 1.61    | 2  | 1     | 97 |  |
| w:h    | .91                  | 30 | .91   | 27 | .91 27  |    | 1     | 18 | .91        | 29                               | .91   | 28 | .91 29  |    | 1     | 16 |  |
| time   | 1.09 50              |    | 1.25  | 14 | 1.31    | 9  | 1     | 52 | 1.45 13    |                                  | 1.80  | 8  | 1.95    | 7  | 1     | 92 |  |
|        |                      |    |       |    |         |    |       |    | OppositeBC |                                  |       |    |         |    |       |    |  |
| ncr    | 1.07 35              |    | 1.11  | 22 | 1.03    | 38 | 1     | 32 | 1.12 36    |                                  | 1.22  | 17 | 1.15 28 |    | 1     | 45 |  |
| nbp    | 1.04 12              |    | 1.02  | 26 | 1.03 22 |    | 1     | 61 | 1.05 12    |                                  | 1.04  | 18 | 1.04 17 |    | 1     | 75 |  |
| width  | 1.13 17              |    | 1.13  | 14 | 1.14 15 |    | 1     | 59 | 1.23       | 6                                | 1.25  | 6  | 1.24    | 6  | 1     | 89 |  |
| height | 1.31                 | 6  | 1.32  | 6  | 1.31    | 4  | 1     | 90 | 1.38       | 1                                | 1.38  | 1  | 1.38    | 1  | 1     | 98 |  |
| area   | 1.48                 | 6  | 1.50  | 7  | 1.49    | 4  | 1     | 87 | 1.72       | 2                                | 1.73  | 2  | 1.72    | 2  | 1     | 97 |  |
| w:h    | .93                  | 33 | .93   | 23 | .93 27  |    | 1     | 19 | .95 29     |                                  | .95   | 29 | .95     | 29 | 1     | 15 |  |
| time   | 1.61 23              |    | 1.96  | 11 | 1.81 13 |    | 1     | 75 | 2.30 10    |                                  | 2.77  | 7  | 2.83    | 6  | 1     | 94 |  |
|        |                      |    |       |    |         |    |       |    | RelPos     |                                  |       |    |         |    |       |    |  |
| ncr    | .82 23               |    | .72   | 47 | .70     | 54 | 1     | 9  | .92 35     |                                  | .90   | 41 | .89     | 42 | 1     | 16 |  |
| nbp    | 1.04 13              |    | 1.03  | 20 | 1.02 26 |    | 1     | 60 | 1.06 10    |                                  | 1.04  | 18 | 1.04 18 |    | 1     | 75 |  |
| width  | 1.11 13              |    | 1.08  | 19 | 1.08 17 |    | 1     | 54 | 1.21       | 6                                | 1.20  | 8  | 1.21    | 6  | 1     | 86 |  |
| height | 1.29                 | 5  | 1.29  | 5  | 1.29    | 5  | 1     | 91 | 1.38       | 1                                | 1.36  | 1  | 1.37    | 1  | 1     | 99 |  |
| area   | 1.43                 | 7  | 1.39  | 9  | 1.40    | 7  | 1     | 81 | 1.67       | 2                                | 1.65  | 2  | 1.66    | 2  | 1     | 97 |  |
| w:h    | .93 27               |    | .93   | 25 | .92     | 31 | 1     | 20 | .94 26     |                                  | .94   | 31 | .94 30  |    | 1     | 15 |  |
| time   | 1.07 48              |    | 1.20  | 12 | 1.24 11 |    | 1     | 51 | 1.43 13    |                                  | 1.76  | 9  | 1.86    | 8  | 1     | 92 |  |

<span id="page-26-0"></span>![](_page_26_Figure_0.jpeg)

Figure 14: Comparison of the three crossing-reduction methods relative to Kieler. For handling local sources and sinks, we used RelPos. In each color, each dot represents one of the 380 original cable plans.

<span id="page-27-0"></span>![](_page_27_Figure_0.jpeg)

Figure 15: Comparison of the three crossing-reduction methods relative to Kieler. For handling local sources and sinks, we have used RelPos. In each color, each dot represents one of the 1140 generated cable plans.

Comparing the running times of the three variants, we note that using FD is about 10–20% slower and using BFS is about 10-20% faster than using RAND. We remark that these percentages refer to the running time of the whole algorithm, not just to the edge orienting phase. This explains why RAND is not necessarily the fastest variant; e.g., if RAND produces many dummy vertices and wider layers, the crossing reduction phase may take longer.

Summing up, we remark that it is worth using a more sophisticated method (FD or BFS) for orienting the undirected edges than just using a random assignment (RAND). The choice between FD and BFS depends on the user's preferences. FD tends to produce fewer crossings and a more balanced aspect ratio. BFS, in contrast, is (slightly) faster and conceptually simpler to understand and to implement. As our main goal is obtaining visually pleasant drawings, we recommend using FD for orienting edges if a (fast) force-directed graph drawing algorithm is available.

#### 5.2. Methods for Crossing Reduction

We first consider the method for handling local sources and sinks in the layer-sweep algorithm. Then we analyze the methods for treating ports and vertices and compare them to Kieler.

Methods for Handling Local Sources and Sinks. Regarding the number of edge crossings, the rather simple approach Relpos outperforms PseudoBC and OppositeBC by far. The second-best method is clearly OppositeBC, whereas PseudoBC performs rather poorly. Regarding the number of bends and the drawing area, all three approaches behave quite similarly. Relpos and PseudoBC are about 50–70 % faster than OppositeBC, with a slight advantage for Relpos.

In our experiments, Relpos turned out to clearly be the best method or at least as good as the others, both in terms of simplicity and in terms of the criteria we measured. Therefore, we recommend Relpos, and in all remaining experiments, we use Relpos.

Methods for Treating Ports and Vertices. In terms of number of edge crossings, the methods Ports and Mixed achieve similar results; both clearly beat the method Vertices. This is in line with our expectation that incorporating distinct port orderings during the whole crossing reduction procedure helps to avoid edge crossings, which crucially depend on the precise order

of ports. However, incorporating all ports (PORTS) instead of only ports at vertices with port pairings (MIXED) does not seem to provide much of an additional benefit. (Recall that MIXED is not a generalization of PORTS, but rather a generalization of VERTICES as the whole accounting is vertex-based instead of port-based.)

Regarding the number of bends and the drawing area, all variants perform similarly well. As expected, using VERTICES is faster than using MIXED, which in turn is faster than PORTS. Using PORTS, the total running time increases by about  $10\text{--}40\,\%$  with respect to VERTICES.

Since we deem a small number of crossings the most important quality measure, we recommend using MIXED or PORTS, which we consider both equally well suited for our application.

## 5.3. Comparison to Kieler

Regarding the number of edge crossings, our new methods outperform the existing algorithm, which has not been designed for these specific port constraints. For the original cable plans, MIXED and PORTS use about  $30\,\%$  fewer crossings and VERTICES still achieves about  $20\,\%$  fewer crossings.

The number of bends is about the same for all variants of our algorithm and Kieler—we use in average at most 6% more bends. We remark that this highly depends on the width of our vertex rectangles. Remember that we have adjusted the algorithm of Brandes and Köpf [6] to handle ports instead of vertices and to limit the distance of ports within the same vertex. Allowing an arbitrary placement also for ports of the same vertex leads to fewer bends, but also produces drawings with overwide vertices. In an earlier version of our algorithm [11], we did not limit the distance between ports within the same vertex. Additionally, our implementations differed in some other minor aspects. This resulted in our variants using much fewer bends than Kieler. Now we have made a design choice to avoid large gaps between ports within a vertex. (Recall that we break vertical alignments if gaps are larger than 16 times the minimum port distance.) We observed that due to this choice (a) the drawings are sufficiently compact and (b) vertex rectangles have an appealing aspect ratio. Moreover, we use roughly as many bends as KIELER does.

The drawings generated by our new algorithm use an about 40% (original plans) and 65% (artificial plans) larger area than the ones generated by Kieler. The main difference comes from a greater height, which we get from more horizontal lines being used for the orthogonal edge routing and for

integrating the intermediate layers that we use for turning dummy vertices. However, as the drawings generated by KIELER tend to be wider than high, using a greater height leads to a better aspect ratio for our variants (better in the sense of being closer to 1, i.e., the bounding box being more square-like).

Also with respect to the running time, KIELER produces its drawing in average a little faster than our algorithm. On the original plans, our variants need in average almost the same time (VERTICES) or about 25 % more time (PORTS). This gap is larger for the generated artificial cable plans, but still seems to be in the range from a factor of 1 to a factor of 2 compared to KIELER. In total numbers, VERTICES, MIXED, PORTS, and KIELER needed in average for the original plans 142 ms, 166 ms, 173 ms, and 127 ms, respectively. The maximum running time that we measured occurred in a cable plan with 354 vertices. It took 1.1 s, 1.3 s, 1.6 s, and 0.6 s, respectively.

In conclusion, we can say that there is no algorithm being superior in all considered aspects. Cognitive studies, however, have shown that a small number of crossings highly influences the readability of a graph drawing for a human user [16, 17]. Our industry partners gave us similar feedback when working with these cable plans. Therefore, we consider reducing the number of crossings by more than a fourth and almost a third to be more important than a slightly smaller drawing area (which is likely to be less readable) and a slightly faster running time (which has to be done only once). Therefore, we recommend using our new algorithm with the variants PORTS or MIXED in combination with RelPos when working with generalized port constraints and—more specifically—when working with cable or circuit plans that are somehow similar to the ones in our experiments.

We remark that the application settings that Kieler is designed for is not the same as for our algorithm, which limits the meaningfulness of this comparison. Moreover Kieler uses more intermediate steps and post-processing steps, e.g., for compactification, which partially explains the smaller drawing area. Kieler also has more additional functionalities and is the overall more mature and established library. Kieler also provided an excellent starting point for our research and helped us to quickly generate some initial layered cable and circuit plans for our industrial partners.

#### 5.4. Generating Pseudo Cable Plans

We concede that the artificial plans that we generated are not perfect as they behave somewhat differently from the original plans for certain criteria. For instance, for the artificial plans the relative advantage of PORTS and Mixed compared to Vertices vanishes. Also our variants perform worse compared to Kieler with respect to the number of edge crossings, drawing area, and running time. Nevertheless, the obfuscation allowed us to make somewhat realistic cable plans publicly available, so that others can validate our experiments in the future.

## 5.5. Open Problems

Our generation procedure may also serve as an entry point for more research in generating pseudo data from original data. This approach can be applied in many domains (and has most probably been applied, in domains we are not aware of). Finding such connections and formalizing the theory behind our obfuscation procedure would be interesting.

We are currently in the process of integrating our algorithm into the software of our industrial partner. We hope to see whether the statistical improvement of our algorithm actually yields advantages in practice. We also hope for practically relevant feedback and problems, which we can theoretically formalize and integrate in our model and algorithm.

We have not yet investigated much the usual tuning of parameters, e.g., the number of repetitions for the crossing reduction phase (currently r = 1) or more repetitions of the whole procedure. Beside minor tuning, our algorithm still leaves room for more radical improvements in many spots. This regards mainly the crossing reduction phase, the node/port placement phase, and the edge routing phase.

It turned out that edge routing gives rise to a cute combinatorial problem (see Section [3.6\)](#page-14-0), which we have not yet solved completely. Let us recapitulate the problem here. We are given a set line segments whose (distinct) endpoints lie on two parallel lines L<sup>i</sup> and Li+1, i.e., a pair of layers in our drawing. Each line segment must be re-drawn as an orthogonal polyline consisting of a vertical, a horizontal, and a second vertical piece. The horizontal pieces must be placed onto parallel horizontal lines `1, `2, . . . lying in between L<sup>i</sup> and Li+1, such that no horizontal pieces overlap and each two polylines intersect at most once. The objective is to minimize the number of horizontal lines being occupied by horizontal pieces.

Recently, Br¨uckner [\[18\]](#page-34-1) and Mittelst¨adt [\[12\]](#page-33-5) have examined this problem a little deeper. The set of lines segments induces a conflict graph C with both directed and undirected edges. An undirected edge means the horizontal pieces of the corresponding two polylines must be placed onto distinct lines, and a directed edge additionally states which horizontal piece must be above which other horizontal piece to avoid double intersections between polylines. Br¨uckner showed that the transitive closure of C is weakly chordal. Orienting the undirected edges of C while minimizing the length of a longest directed path would provide an assignment of horizontal pieces to lines, which uses a minimum number of lines. Mittelst¨adt showed that our greedy approach is optimal for only left-going (right-going) edges and hence a 2-approximation for the combination of both. It would be interesting to see an optimal polynomial-time algorithm or to show that the problem is NP-hard and to give a better approximation algorithm if possible.

We are also interested in more domains where we can apply the concept of layered graph drawing with generalized port constraints—both for directed and undirected graphs. Beside cable plans, applications may include circuit plans, IT network plans, UML diagrams, data-flow networks, knowledge graphs, and many more.

## References

- <span id="page-32-0"></span>[1] K. Sugiyama, S. Tagawa, M. Toda, Methods for visual understanding of hierarchical system structures, IEEE Trans. Syst. Man Cybern. 11 (2) (1981) 109–125. [doi:10.1109/TSMC.1981.4308636](https://doi.org/10.1109/TSMC.1981.4308636).
- <span id="page-32-1"></span>[2] T. C. Biedl, B. Madden, I. G. Tollis, The three-phase method: A unified approach to orthogonal graph drawing, Int. J. Comput. Geom. Appl. 10 (6) (2000) 553–580. [doi:10.1142/S0218195900000310](https://doi.org/10.1142/S0218195900000310).
- <span id="page-32-2"></span>[3] C. D. Schulze, M. Sp¨onemann, R. von Hanxleden, Drawing layered graphs with port constraints, J. Vis. Lang. Comput. 25 (2) (2014) 89– 106. [doi:10.1016/j.jvlc.2013.11.005](https://doi.org/10.1016/j.jvlc.2013.11.005).
- <span id="page-32-3"></span>[4] A. Okka, U. Dogrusoz, H. Balci, CoSEP: A compound spring embedder layout algorithm with support for ports, Inform. Vis. 20 (2–3) (2021) 151–169. [doi:10.1177/14738716211028136](https://doi.org/10.1177/14738716211028136).
- <span id="page-32-4"></span>[5] P. Eades, S. Whitesides, Drawing graphs in two layers, Theor. Comput. Sci. 131 (2) (1994) 361–374. [doi:10.1016/0304-3975\(94\)90179-1](https://doi.org/10.1016/0304-3975(94)90179-1).
- <span id="page-32-5"></span>[6] U. Brandes, B. K¨opf, Fast and simple horizontal coordinate assignment, in: P. Mutzel, M. J¨unger, S. Leipert (Eds.), Proc. 9th Int. Symp. Graph Drawing (GD'01), Vol. 2265 of LNCS, Springer, 2002, pp. 31–44. [doi:](https://doi.org/10.1007/3-540-45848-4_3) [10.1007/3-540-45848-4\\\_3](https://doi.org/10.1007/3-540-45848-4_3).

- <span id="page-33-0"></span>[7] U. Brandes, J. Walter, J. Zink, [Erratum: Fast and simple horizontal](http://arxiv.org/abs/2008.01252) [coordinate assignment,](http://arxiv.org/abs/2008.01252) CoRR abs/2008.01252 (2020). URL <http://arxiv.org/abs/2008.01252>
- <span id="page-33-1"></span>[8] T. M. J. Fruchterman, E. M. Reingold, Graph drawing by force-directed placement, Softw. – Pract. & Exper. 21 (11) (1991) 1129–1164. [doi:](https://doi.org/10.1002/spe.4380211102) [10.1002/spe.4380211102](https://doi.org/10.1002/spe.4380211102).
- <span id="page-33-2"></span>[9] F. Lipp, A. Wolff, J. Zink, Faster force-directed graph drawing with the well-separated pair decomposition, Algorithms 9 (3) (2016) 53. [doi:](https://doi.org/10.3390/a9030053) [10.3390/a9030053](https://doi.org/10.3390/a9030053).
- <span id="page-33-3"></span>[10] E. R. Gansner, E. Koutsofios, S. C. North, K. Vo, A technique for drawing directed graphs, IEEE Trans. Softw. Engineer. 19 (3) (1993) 214–230. [doi:10.1109/32.221135](https://doi.org/10.1109/32.221135).
- <span id="page-33-4"></span>[11] J. Walter, J. Zink, J. Baumeister, A. Wolff, Layered drawing of undirected graphs with generalized port constraints, in: Proc. 28th Int. Symp. Graph Drawing & Network Vis. (GD'20), Vol. 12590 of LNCS, Springer, 2020, pp. 220–234. [doi:10.1007/978-3-030-68766-3\\\_18](https://doi.org/10.1007/978-3-030-68766-3_18).
- <span id="page-33-5"></span>[12] F. Mittelst¨adt, [About coloring of generalized interval graphs,](https://www1.pub.informatik.uni-wuerzburg.de/pub/theses/2022-mittelstaedt-masterarbeit.pdf) master's thesis, Institut f¨ur Informatik, Universit¨at W¨urzburg, in German (2022). URL [https://www1.pub.informatik.uni-wuerzburg.de/pub/](https://www1.pub.informatik.uni-wuerzburg.de/pub/theses/2022-mittelstaedt-masterarbeit.pdf) [theses/2022-mittelstaedt-masterarbeit.pdf](https://www1.pub.informatik.uni-wuerzburg.de/pub/theses/2022-mittelstaedt-masterarbeit.pdf)
- <span id="page-33-6"></span>[13] [PRALINE data structure and layouting algorithm](https://github.com/j-zink-wuerzburg/praline) (2020). URL <https://github.com/j-zink-wuerzburg/praline>
- <span id="page-33-7"></span>[14] [PRALINE pseudo plans – algorithm and data sets](https://github.com/j-zink-wuerzburg/\ pseudo-praline-plan-generation) (2020). URL [https://github.com/j-zink-wuerzburg/](https://github.com/j-zink-wuerzburg/\ pseudo-praline-plan-generation) [\pseudo-praline-plan-generation](https://github.com/j-zink-wuerzburg/\ pseudo-praline-plan-generation)
- <span id="page-33-8"></span>[15] [Eclipse layout kernel \(ELK\)](https://www.eclipse.org/elk/) (2020). URL <https://www.eclipse.org/elk/>
- <span id="page-33-9"></span>[16] H. C. Purchase, D. A. Carrington, J. Allder, Empirical evaluation of aesthetics-based graph layout, Empirical Softw. Engin. 7 (3) (2002) 233– 255. [doi:10.1023/A:1016344215610](https://doi.org/10.1023/A:1016344215610).

- <span id="page-34-0"></span>[17] C. Ware, H. C. Purchase, L. Colpoys, M. McGill, Cognitive measurements of graph aesthetics, Inform. Vis. 1 (2) (2002) 103–110. [doi:](https://doi.org/10.1057/palgrave.ivs.9500013) [10.1057/palgrave.ivs.9500013](https://doi.org/10.1057/palgrave.ivs.9500013).
- <span id="page-34-1"></span>[18] L. Br¨uckner, [Orthogonal drawing as a coloring problem in per](https://www1.pub.informatik.uni-wuerzburg.de/pub/theses/2021-brueckner-bachelor.pdf)[fect graphs,](https://www1.pub.informatik.uni-wuerzburg.de/pub/theses/2021-brueckner-bachelor.pdf) bachelor's thesis, Institut f¨ur Informatik, Universit¨at W¨urzburg, in German (2021).
  - URL [https://www1.pub.informatik.uni-wuerzburg.de/pub/](https://www1.pub.informatik.uni-wuerzburg.de/pub/theses/2021-brueckner-bachelor.pdf) [theses/2021-brueckner-bachelor.pdf](https://www1.pub.informatik.uni-wuerzburg.de/pub/theses/2021-brueckner-bachelor.pdf)

# <span id="page-35-0"></span>Appendix A. Cable Plan Drawings

Next, we provide drawings of six cable plans (three original plans and three pseudo plans). For each plan, there is a drawing generated by our algorithm using FD, PORTS and RELPOS, and there is another drawing generated using KIELER. The drawings have been generated automatically in a run where each plan has been drawn ten times and the best drawing (with respect to the number of crossings) has been kept. Port pairings are indicated by line segments inside a vertex.

![](_page_35_Picture_2.jpeg)

Figure A.16: Original cable plan (anonymized) from the large data set with 69 vertices and 104 crossings drawn by our algorithm using FD, PORTS and RELPOS.

![](_page_36_Figure_0.jpeg)

Figure A.17: Original cable plan (anonymized) from the large data set with 69 vertices and 162 crossings drawn using Kieler.

![](_page_37_Figure_0.jpeg)

Figure A.18: Pseudo cable plan generated from the large data set with 101 vertices and 138 crossings drawn by our algorithm using FD, PORTS and RELPOS.

![](_page_38_Figure_0.jpeg)

Figure A.19: Pseudo cable plan generated from the large data set with 101 vertices and 149 crossings drawn using Kieler.

![](_page_39_Picture_0.jpeg)

Figure A.20: Original cable plan (anonymized) from the readable data set with 50 vertices and 52 crossings drawn by our algorithm using FD, Ports and RelPos.

![](_page_40_Picture_0.jpeg)

Figure A.21: Original cable plan (anonymized) from the readable data set with 50 vertices and 71 crossings drawn using Kieler.

![](_page_41_Figure_0.jpeg)

Figure A.22: Original cable plan (anonymized) from the readable data set with 225 vertices and 391 crossings drawn by our algorithm using FD, PORTS and RELPOS.

![](_page_42_Picture_0.jpeg)

Figure A.23: Original cable plan (anonymized) from the readable data set with 225 vertices and 562 crossings drawn using Kieler.

![](_page_43_Picture_0.jpeg)

Figure A.24: Pseudo cable plan generated from the readable data set with 39 vertices and three crossing drawn by our algorithm using FD, Ports and RelPos.

![](_page_44_Figure_0.jpeg)

Figure A.25: Pseudo cable plan generated from the readable data set with 39 vertices and three crossings drawn using Kieler.

![](_page_45_Figure_0.jpeg)

Figure A.26: Pseudo cable plan generated from the readable data set with 144 vertices and 86 crossings drawn by our algorithm using FD, PORTS and RELPOS.

![](_page_46_Figure_0.jpeg)

Figure A.27: Pseudo cable plan generated from the readable data set with 144 vertices and 157 crossings drawn using Kieler.