# A Simple Pipeline for Orthogonal Graph Drawing

Tim Hegeman[n](https://orcid.org/0009-0008-4770-3391) and Alexander Wol[ff](https://orcid.org/0000-0001-5872-718X)

Universität Würzburg, Würzburg, Germany hegemann@informatik.uni-wuerzburg.de

Abstract. Orthogonal graph drawing has many applications, e.g., for laying out UML diagrams or cableplans. In this paper, we present a new pipeline that draws multigraphs orthogonally, using few bends, few crossings, and small area. Our pipeline computes an initial graph layout, then removes overlaps between the rectangular nodes, routes the edges, orders the edges, and nudges them, that is, moves edge segments in order to balance the inter-edge distances. Our pipeline is flexible and integrates well with existing approaches. Our main contribution is (i) an effective edge-nudging algorithm that is based on linear programming, (ii) a selection of simple algorithms that together produce competitive results, and (iii) an extensive experimental comparison of our pipeline with existing approaches using standard benchmark sets and metrics.

Keywords: Orthogonal graph drawing · Edge routing · Edge nudging Experimental evaluation

·

### <span id="page-0-0"></span>1 Introduction

Due to its many applications, the orthogonal drawing style has been studied extensively in Graph Drawing. One of the milestones in the development of efficient algorithms for this domain was Tammasia's Topology–Shape–Metric framework [\[19\]](#page-16-0) which showed that embedded planar graphs with a vertex degree of at most 4 can be laid out efficiently, using the minimum number of bends. The restriction to degree 4 comes from the fact that the framework represents vertices by (grid) points. For practical purposes, however, the restriction to (embedded) planar graphs of constant degree is prohibitive. This triggered many practical approaches to orthogonal graph drawing. For example, the three-phase method of Biedl et al. [\[1\]](#page-14-0) draws normalized graphs (that is, graphs without self-loops and leaves) with vertices in general position (that is, on different grid lines) with "small" vertex boxes on an quadratic size grid using at most one bend per edge. For compaction, Biedl et al. referred to Lengauer's book [\[10\]](#page-16-1) on VLSI layout, which is also relevant for orthogonal graph drawing. Building on earlier work [\[3,](#page-14-1)[5,](#page-16-2)[16,](#page-16-3)[20\]](#page-16-4), Kieffer et al. [\[8\]](#page-16-5) introduced Hola ("Human-like Orthogonal Network Layout"), a multi-step approach for drawing graphs orthogonally. They partition the input graph and use different layout strategies for different parts: stress minimization for the graph core and specialized code for tree-like subgraphs.

Schulze et al. [\[17\]](#page-16-6) presented the orthogonal graph drawing library Kieler [\[15\]](#page-16-7) that took special care of so-called port constraints. They allow the user to specify on which side of a vertex box an edge must be attached, which is important, for example, for UML diagrams. Zink et al. [\[21\]](#page-16-8) presented the Praline library, which generalizes port constraints by introducing port groups and port pairings, which are useful for drawing cableplans. Both the approaches of Schulze et al. and Zink et al. arrange nodes on layers and use the framework of Sugiyama et al. [\[18\]](#page-16-9) for layered graph drawing (although they do not assume input graphs to be directed), among others, in order to reduce edge crossings.

Whereas most graph drawing algorithms place labels into vertex boxes, Binucci et al. [\[2\]](#page-14-2) also incorporated edge labels. Using mixed integer programming, they can draw sparse graphs with vertex and edge labels of up to 100 vertices.

We considered orthogonal graph layout in a third-party-funded project with two industrial partners with different backgrounds. One of them produces network management software; the other produces software for drawing cableplans of complicated, highly configurable machines. Both asked for layouts that work well on mobile devices such as tablet computers used by, for example, technicians who service harvesting machines in the field.

Rather than a monolithic software package, they were interested in a highly configurable, flexible pipeline whose parts can easily be exchanged in order to meet the various needs of their customers. Still, they insisted on a number of basic requirements. The drawings computed by our algorithm must be orthogonal, that is, edges are drawn as sequences of axis-aligned segments and vertices are represented by non-overlapping boxes (i.e., axis-aligned rectangles). Also, the user must be able to specify a minimum object distance δmin to be respected by vertex boxes and edge segments.

In terms of quality, we agreed upon standard graph drawing criteria such as few crossings, few bends, small area, good aspect ratio, small total edge length, and small edge length variance. With mobile applications in mind, using small area becomes our key objective. However, rather than an algorithm that excels in one of these metrics (and fails badly in another), our partners were interested in allrounders that are sufficiently fast and generally perform well.

Our Contribution. We set up a layout pipeline with three variants. For the first variant (Force), we use a force-directed layout algorithm [\[6\]](#page-16-10) to place the vertices of a given graph G as points (ignoring their boxes). Then we center the vertex boxes on these points. If some of them overlap, we call an overlap removal algorithm of Nachmanson et al. [\[11\]](#page-16-11). Instead of these three steps, for the second variant (Hybrid1), we used the vertex placement computed by Praline. In both cases, we apply the following steps that we describe in detail in Section [2.](#page-2-0) Port assignment: We assign the endpoints of the edges to the sides of the vertex boxes. Routing graph construction: We construct an auxiliary grid-like graph H. Edge routing and path ordering: We route (and order) the edges of G along the edges of H. Our path ordering is based on existing techniques [\[7,](#page-16-12)[12,](#page-16-13)[13\]](#page-16-14). Now each edge of G consists of a path of axis-aligned segments. Edge nudging: In this final step, we distribute the path segments so that they partition the available space between the vertex boxes as evenly as possible. As a third variant (Hybrid2), we initialize our pipeline with both the vertex positions and the edge routing computed by Praline and apply only the nudging step as a post-processing.

Our main contribution is (i) the edge nudging step, (ii) our simple and flexible pipeline as a whole, and (iii) an experimental comparison with the state-of-the-art orthogonal layout libraries Hola<sup>1</sup> [8] and Praline<sup>2</sup> [21] on two standard benchmark sets (see Section 3). Praline has already been compared with Kieler, and performed similarly well or even slightly better [21]. Hola has been compared to the *orthogonal style* automatic layout of YFILES<sup>3</sup>; Hola outperformed YFILES almost universally in a user study with 89 participants [8].

As it turns out, our pipeline proves to be a good allrounder that performs well in many of the metrics mentioned above. Due to careful nudging, our pipeline yields very compact layouts, whereas its competitors usually produce fewer crossings and bends. Depending on the variant, our pipeline takes slightly less or about twice as much time than Praline. It is much faster than Hola.

Our source code is available at https://github.com/hegetim/wueortho.

#### <span id="page-2-0"></span>2 Our Pipeline

In order to fine-tune the layout for different requirements (as discussed in Section 1), we designed our pipeline as a sequence of mostly independent, interchangeable, and self-contained steps that we describe in detail in this section.

The input for our pipeline is a multigraph G with vertex set V(G) of size n and edge multiset E(G) of size m. We explicitly allow our graphs to have self-loops and handle them in the *port assignment* step. Each vertex comes with a (textual) vertex label or directly with a *vertex box*, that is, an axis-aligned rectangle. Given a text label, we compute a box that fits the label (in some standard font).

Our pipeline consists of several simple algorithms for specific subproblems of orthogonal graph drawing; see Fig. 1 for an overview. The main steps in our pipeline are vertex layout, overlap removal, port assignment, construction of the routing graph, edge routing, path ordering, and edge nudging. Below we detail most of these steps. For the remaining, we use standard algorithms, see "Pipeline Variants", Section 3.

**Port Assignment.** Each edge connects one or two vertices that are represented by rectangular boxes. We call the start point and the end point of an edge its *ports*. Ports lie on the boundary of the vertex boxes that an edge connects. Port positions can either be specified in the input, or they are set by our pipeline as follows (before the edge routes are determined).

For each edge uv, we first determine the sides of the boxes of u and v on which we place the ports of uv. Let  $s_{uv}$  be the straight-line segment that connects the

<span id="page-2-1"></span><sup>1</sup> see https://www.adaptagrams.org/

<span id="page-2-2"></span><sup>&</sup>lt;sup>2</sup> see https://github.com/j-zink-wuerzburg/praline

<span id="page-2-3"></span><sup>3</sup> see https://www.yworks.com/products/yfiles

<span id="page-3-0"></span>![](_page_3_Figure_0.jpeg)

Fig. 1: Our flexible pipeline of simple algorithms for orthogonal graph drawing.

centers of the boxes of u and v. We usually assign the ports to those box sides that intersect suv. To avoid situations where an edge uv would have to be drawn as a Z-shape according to the rule above, we adjust the rule as follows. We split each side evenly into four pieces. If suv intersects a side in the first or last piece of the side, we instead reassign one of the two ports such that uv can be drawn as an L-shape that bends away from the barycenter of the vertex boxes' center points. (We do not actually route uv now, we just use geometry to place its ports.) The order along a side of vertex u is then determined by the circular order of the segments of type suv, where v is a neighbor of u. Multi-edges require special care regarding their order within a side. They are routed next to each other without crossings. Self-loops get neighboring ports assigned to the least populated side. When all ports have been assigned to a box, we evenly distribute the ports on each side.

Routing Graph Construction. We route each edge of the input graph along an obstacle-avoiding path in a routing graph H whose vertices are the ports and the potential bend points of edge routes. This graph forms a partial grid with gaps around the vertex boxes. A precise definition follows below.

The intuition for our routing graph is that edges get routed through horizontal and vertical channels. We describe only vertical channels. Horizontal channels are defined symmetrically. For a pair of vertex boxes (u, v) where v is entirely to the right of u, we define its vertical channel as the largest axis-aligned rectangle whose vertical sides touch the right side of u and the left side of v and that is interior-disjoint from all vertex boxes – if such an empty rectangle exists for (u, v). For each box u we keep only the channel to the right of u that has the smallest width. For this step, we interpret the left and right boundaries of the drawing as vertex boxes of zero width and infinite height. In Fig. [2,](#page-4-0) the orange boxes depict the vertical channels. Note that some of these channels overlap. We can find all channels in O(n log n) time with a sweepline algorithm.

For each vertical channel, we define a vertical line segment that spans the channel's entire height as its representative. If possible, we choose an appropriate

<span id="page-4-0"></span>![](_page_4_Figure_0.jpeg)

Fig. 2: Routing graph construction: vertical channels (orange hatched) and their representatives (red). Dotted representatives have been sorted out. Note that ports are omitted and all representatives are the vertical center line of their channel. Black crosses mark where horizontal representatives (not shown) intersect. Those will host vertices in the final routing graph.

line segment starting in a port. Otherwise, we choose the center line of the channel. As a further optimization, we ignore every vertical channel C that intersects another channel C ′ such that the projection of C on the y-axis is contained in that of C ′ . See the dotted red segments in Fig. [2.](#page-4-0) We define representatives for horizontal channels symmetrically. We add additional representatives for each remaining port. We can find all representatives using the same sweepline algorithm as above in O(m log m) time, assuming n ∈ O(m).

The routing graph H has a vertex for each port and for each intersection point between a vertical and a horizontal representative. It has an edge between each pair of vertices that are consecutive along a representative. Let M be the number of edges of H. Again assuming n ∈ O(m), we have M ∈ O(m<sup>2</sup> ) since there are at most 4n channels (one per side for each vertex box) and 2m ports.

Edge Routing. In the next step, for each edge we connect its endpoints (which are ports and thus vertices in the routing graph H) by a shortest path in H. Our approach for edge routing is similar to that of Wybrow et al. [\[20\]](#page-16-4) except that they use the A<sup>∗</sup> search for computing shortest paths whereas we use Dijkstra's algorithm (for simplicity). Recall that H is a partial grid graph. Among all shortest paths, we choose a bend-minimal one by augmenting the state used in Dijktra's algorithm. For each partial path ending in a node v, in addition to the length of the path, we store the number of bends and the direction of entry when entering v. In the following, we refer to routed edges as paths. Each such path can be found in O(M log M) time.

The edge routing algorithm of Wybrow et al. does not take crossings into account. Therefore, as a post-processing, we apply an additional crossing reduction step. Whenever two paths cross each other more than once, we replace the section between the first and last shared vertex in one path with the corresponding section of the other. This ensures that, eventually, every pair of edges crosses at most once.

<span id="page-5-0"></span>![](_page_5_Figure_0.jpeg)

![](_page_5_Picture_2.jpeg)

(b) Edge paths ordered with our modified version of the algorithm.

Fig. 3: Path ordering: The algorithm of Pupyrev et al. assigns each segment an arbitrary direction. This can result in additional bends in the geometric realization (to the right). For orthogonal routing, we therefore preassign directions for horizontal and vertical segments.

**Path Ordering.** We now know, for each edge of the routing graph H, the set of edge paths routed over this segment. Where several edge paths (forming an edge bundle) share a segment, we determine a path order that minimizes crossings.

For non-orthogonal routing graphs, Pupyrev et al. [13] observed that the problem of determining such a path order is computationally equivalent to the metro-line crossing minimization (MLCM) problem: Let G be a plane graph (such as the routing graph), and let P be a set of simple paths in  $\widetilde{G}$ . For each edge e in  $E(\widetilde{G})$ , find an order of all paths that contain e that minimizes the number of crossings among all pairs of paths.

We use the algorithm of Pupyrev et al. [13] for our case where all edges are incident to unique ports (which makes MLCM efficiently solvable). When sorting paths in an edge bundle, for each pair of paths, they consider the directions the paths take after leaving their common subpath at a fork vertex. In Fig. 3a, for example, the leftmost vertex is a fork vertex for paths a and b. With a leaving to the top, it will be ordered above of b. For each segment (i.e., edge in H) such an ordering of paths has to be found. They fix an arbitrary direction that determines where to look for either a fork vertex or a segment that has already been processed (see the gray arrowheads in Fig. 3). Crossings are unavoidable if the path orders at the start and end of the common subpath differ. Pupyrev et al. process the segments in arbitrary order. Still, they introduce at most one crossing for each pair of paths in an edge bundle and only if such a crossing is unavoidable. For example, paths a and b in Fig. 3a have an unavoidable crossing.

In our orthogonal setting, if two paths change order between two adjacent edges of H (see the red lightning in Fig. 3a (left)), then we have to introduce two additional bends in a Z-shaped fashion in their geometric realization (see Fig. 3a (right)). In order to avoid such situations, we preassign directions for all segments based on their orientation (left for horizontal segments and down for

<span id="page-6-0"></span>![](_page_6_Figure_0.jpeg)

- (a) edge order indicated by colored boxes
- (b) defining the constraint graph

Fig. 4: Edge nudging: Given an edge order on the vertical edge segments, we define horizontal separation constraints between vertical segments, left and right borders of vertex boxes, and two dummy segments (black bars). In (b) segments are partially nudged for readability.

vertical ones; see Fig. [3b\)](#page-5-0). Crossings now happen only where the orientation of segments changes (i.e., at bend points of paths). Such crossings can be realized without additional edge bends; see the crossing at the green checkmark in Fig. [3b.](#page-5-0) Therefore, before the next step, we join consecutive collinear segments of the same path. Then, in any path, the orientation of the segments alternates.

Applied to the graph H, our modification of the algorithm of Pupyrev et al. runs in O(M k log m) time, where k is the total number of segments in all paths.

Edge Nudging. In the last step of our pipeline, we aim to balance the distances between the path segments within their channels. Our algorithm has two modes called constrained nudging, when vertex and port positions must not be altered, and full nudging, when a minimum distance between path segments and vertex boxes must be met, but boxes can be moved and, if necessary, enlarged. Both modes use basic linear programming (LP) to optimize segment distances. They process horizontal and vertical distances independently.

We now describe the horizontal pass. The vertical pass works symmetrically. First, we determine the horizontal order χ of all vertical path segments, the left and right borders of all vertex boxes, and the two vertical sides of a (slightly enlarged) bounding box of our instance (see the black bars in Fig. [4b\)](#page-6-0). The order of the objects in χ is determined by their x-coordinate. The two dummy segments are the first and last elements of χ. It remains to define the order of objects with identical x-coordinate. We assume non-intersecting, non-touching vertex boxes. Where path segments overlap, the path order determined in the previous section applies; see the colored boxes in Fig. [4a.](#page-6-0) Right (left) borders of vertex boxes are inserted into χ before (after) any path segment with the same x-coordinate. The order of non-overlapping path segments with the same x-coordinate is arbitrary.

<span id="page-7-0"></span>![](_page_7_Figure_0.jpeg)

- (a) without transitive constraints
- (b) components of the constraint graph

Fig. 5: Common steps of edge nudging: (a) After removing transitive arcs, pink arcs remain between unmovable objects. Brown arcs get distance variables. (b) The constraint graph is split at barriers (black bars). All constraints from arcs in the same component share their distance variables.

Given χ, we define the constraint graph Gχ, the directed acyclic graph that has a vertex for each object as defined above, and an arc from object u to object v if the vertical dimensions of these objects overlap, u comes before v in χ, and there is no other vertically overlapping object in between. If this is the case, u will be drawn to the left of v. Edges of this constraint graph will yield separation constraints of the form u<sup>x</sup> + δ ≤ v<sup>x</sup> in the LP, where u<sup>x</sup> and v<sup>x</sup> are the x-coordinates of u and v, respectively, and δ is either a non-negative variable or the user-defined minimum distance δmin between them.

Let N = 4n+m+b be the number of sides of the vertex boxes plus the number of edge segments (i.e., the number of edges plus the number of bends). Then the constraint graph can be constructed in O(N log N) time, using a sweepline algorithm of Dwyer et al. [\[5\]](#page-16-2). They showed that the number of edges in the constraint graph is linear in N and that the separation constraints derived from the edges of G<sup>χ</sup> guarantee a horizontally overlap-free drawing. Next, we decide which constraints share the same distance variables of type δ, which we will then maximize. Wider channels with few segments allow for larger gaps than small crowded channels. To obtain a balanced solution, we need to avoid situations where two distance variables work against each other.

To identify preferably small sets of constraints that share the same distance variable, we apply the following operations to the constraint graph. We remove all transitive arcs, i.e., arcs uw where also arcs uv and vw exist in the graph. Constraints from these arcs are redundant. We remove all arcs between objects that do not move in constrained nudging mode, that is, the sides of vertex boxes and edge segments incident to ports; see the purple arrows in Fig. [5a.](#page-7-0) Then, the graph is split into components (the green areas in Fig. [5b\)](#page-7-0) that are confined by unmovable objects or by dummy segments (the big black bars in Fig. [5b\)](#page-7-0). All constraints derived from arcs of the same component get the same distance variable.

<span id="page-8-0"></span>![](_page_8_Figure_0.jpeg)

**Fig. 6:** Results of a horizontal nudging phase: (a) optimization nudges objects apart, (b) in full nudging mode, objects must maintain a given minimum distance  $\delta_{\min}$ . Note that vertex ③ has been slightly enlarged to make room for the ports of edges a and b.

In constrained nudging mode, for each movable or dummy segment, we replace its position by a *position variable* in all related constraints. Finally, our LP minimizes

$$|W|(\omega - \alpha) - \sum_{\delta \in W} \delta,$$

where  $\alpha$  and  $\omega$  are the position variables of the left and right dummy segments, respectively, and W is the set of distance variables. The factor |W| is required to prevent the constraints involving distance variables from pushing the dummy segments towards infinity. The result is shown in Fig. 6a. Objects are separated with space between them equivalent to at least the values of the respective distance variables.

In full nudging mode we allow both, the port segments and the borders of the vertex boxes, to be moved by the nudging procedure in order to maintain a minimum object distance  $\delta_{\min}$  and to control the total edge length. We allow vertex boxes to grow, if necessary, but not to shrink. Therefore, we use position variables for all sides of vertex boxes and edge segments instead of fixed positions.

In addition to the constraints from the constrained mode (brown arrows in Fig. 5b), we introduce, for each vertex box b of original width  $w_b$  (as specified in the input) a separation constraint  $b^{\rm R} - b^{\rm L} \geq w_b$  where  $b^{\rm L}$  and  $b^{\rm R}$  are the position variables of the left and right sides of b, respectively. For all arcs that have not been transitively removed (see brown and pink arrows in Fig. 5a), we add separation constraints with a constant distance of  $\delta_{\rm min}$ .

In order to establish a hierarchy in optimization, we weight our objective by adding constant factors. Let W be the set of distance variables, let  $S_{\rm H}$  be the set of horizontal segments, and let B the set of vertex boxes. We use the term  $b^{\rm R} - b^{\rm L}$  for the width of box  $b \in B$  and  $s^{\rm R} - s^{\rm L}$  for the length of segment  $s \in S_{\rm H}$ . Now we have our LP minimize the sum of the widths of the vertex boxes and

the lengths of the segments minus the sum of the distance variables, that is,

$$2(|W| + |S_{\rm H}|) \left(\omega + \sum_{b \in B} (b^{\rm R} - b^{\rm L})\right) + 2\sum_{s \in S_{\rm H}} (s^{\rm R} - s^{\rm L}) - \sum_{\delta \in W} \delta.$$

Fig. [6b](#page-8-0) shows the result for the example depicted in Fig. [4a.](#page-6-0) Multiple phases of nudging can be repeatedly applied to optimize compactness and edge lengths. To get rid of unnecessary bends, we simply set the separation distance of constraints between segments of the same path to zero.

### <span id="page-9-0"></span>3 Experiments

We considered three variants (described below) of our pipeline, and compared them to the state-of-the-art orthogonal layout libraries Praline and Hola.

Benchmark Sets. Our pipeline has been implemented as part of a third-partyfunded project with two industrial partners that suggested two benchmark sets from their respective domains. The first benchmark set is called Internet Topology Zoo[4](#page-9-1) [\[9\]](#page-16-15). The data set includes textual vertex labels of varying length.

The second dataset is called Pseudo-cableplans. The graphs have been part of a benchmark set for orthogonal graph drawing by Zink et al.[5](#page-9-2) [\[21\]](#page-16-8). We removed some domain-specific peculiarities such as special vertex pairing and port grouping constraints, and we replaced each hyperedge e by a new dummy vertex v<sup>e</sup> that we connected to every vertex in e. The labels in this dataset are fixed-length or empty (the dummy vertices).

In both benchmark sets, we kept only the largest connected component of each graph. Although preliminary tests showed some good results, Hola officially does not support multigraphs. Therefore, we removed all but the first occurrence of each multi-edge and all self-loops. Furthermore, we removed all graphs where Hola crashed or took more than 10 minutes. Note that our pipeline correctly draws every connected instance in the original datasets, including multi-edges and self-loops.

So for our experiments we used 260 simple graphs derived from the original 261 multigraphs of the Internet Topology Zoo and 1,026 graphs derived from the original 1,139 Pseudo-cableplans. Figure [7](#page-10-0) shows the edge density distribution of the graphs in the two benchmark sets. We set the default dimensions of the vertex boxes to 12 × 38 (pixels) and widened them if necessary to accommodate the label text and to fit all incident edges (with gaps of 18 pixels).

Pipeline Variants. We set up three variants of our pipeline. In the first variant, Force, we use a simple force-directed layout algorithm [\[6\]](#page-16-10) to place the vertices

<span id="page-9-1"></span><sup>4</sup> see <http://www.topology-zoo.org/index.html>

<span id="page-9-2"></span><sup>5</sup> see <https://github.com/j-zink-wuerzburg/pseudo-praline-plan-generation>

<span id="page-10-0"></span>![](_page_10_Figure_0.jpeg)

Fig. 7: Number of vertices and edges for each graph in the two datasets. Semi-transparent markers represent the original multigraphs.

as points (ignoring their boxes). Then, we apply the GTREE Algorithm by Nachmanson et al. [11] to remove overlaps. In the second variant, *Hybrid*, we use vertex positions computed by Praline [21]. These variants both go through the steps port distribution, routing graph construction, edge routing, edge ordering, and full edge nudging as described in the previous sections. Full nudging is applied horizontally, then vertically, and then once more horizontally. As a third variant *Hybrid*, we initialize our pipeline with both the vertex positions and the edge routing computed by Praline and apply only the nudging step as a post-processing. All pipeline steps are implemented in Scala and dynamically configurable for various setups. We use the GLOP<sup>6</sup> optimizer for LP-solving.

Metrics. To assess the quality of graph drawings many metrics have been proposed. In our experiments we use edge crossings, edge bends, total edge length, variance in edge length, area, aspect ratio, and minimum object distance ( $\delta_{\min}$ ). These will be discussed below.

It has been shown (e.g., in a study by Purchase [14]) that drawings with fewer edge crossings and bends simplify several tasks related to graph understanding and navigation. A study by Dwyer et al. [4] suggests that users benefit from graph drawings with low variance in edge length. When drawing graphs with more than 30 vertices, scaling becomes an issue as text labels tend to become unreadably small and overly long edges become hard to follow. Therefore, we include metrics assessing the compactness of drawings in our comparisons, namely total edge length and the area of the bounding box. For a drawing with a bounding box of width w and height h, we define aspect ratio as  $\max(w, h) / \min(w, h)$ . This yields a value in the range  $[1, \infty)$ . We consider lower aspect ratios better and squares (with aspect ratio 1) optimal. In order to ensure a fair comparison with metrics sensitive to scaling, we also include the minimum object distance  $\delta_{\min}$ .

<span id="page-10-1"></span><sup>&</sup>lt;sup>6</sup> see https://developers.google.com/optimization

We configure a minimum value (or target value, if no minimum is supported) of 12 pixels and report deviations.

Comparison. We compared our pipeline to the following two libraries. Praline [21] is based on the well-known Sugiyama framework [18] for layered graph drawing. Praline differs from the original framework especially in terms of edge routing and port placement. Layering-based algorithms tend to produce few crossings and balanced results. Hola [8] is a multi-stage algorithm that decomposes the input into trees and a connected core that is drawn using stress-minimization and overlap removal. The trees are drawn using a specialized layout algorithm, and the tree drawings are then inserted into the drawing of the whole graph. For our comparison, we used the default settings regarding vertex distances and ideal edge length in Hola. We conducted small-scale experiments that confirm that the defaults yield a good compromise between compactness and readability (i.e., sufficiently large  $\delta_{\min}$ ).

Results. See Table 1 and Fig. 8 for the results of our experiments. Concerning the number of crossings, we see a weakness of the simplistic approach of our pipeline. On average, FORCE produced over twice as many crossings as the best results on the Pseudo-cableplans and nearly five times as many on the Internet Topology Zoo graphs. Hybrid, combining Praline vertex positions and our pipeline, on the other hand, produced only 41% more crossings on the Pseudo-cableplans and 54% more crossings on the Internet Topology Zoo graphs compared to the best results. Hybrid per construction produces the same number of crossings as Praline. Bad vertex placement also hurts down the pipeline. As we can see, the Hybrid variants are almost consistently better than Force with two exceptions: edge length variance and aspect ratio. However, in terms of aspect ratio, the only outlier is Hola, performing nearly 30% worse than the others on the Internet Topology Zoo.

Hola shows an impressive performance in terms of crossings and creates by far the fewest bends. But this comes at a cost of a very large drawing area and overly long edges. Hola considers  $\delta_{\min}$  an optimization goal, not a strict requirement. In the majority of cases the target value of 12 px could be maintained. Praline, however, surprised us, too. Not maintaining  $\delta_{\min}$  was confirmed to us being a bug in the current Praline implementation by the authors.

Overall, the HYBRID variants of our pipeline show good and very consistent results with HYBRID2, surpassing PRALINE in all quality metrics. It produces leading results with respect to area, total edge length, and edge length variance while reliably maintaining the given minimum object distance.

Running Time. We evaluated the running times of our pipeline using 300 random multigraphs with 5 to 150 vertices and average vertex degree 4. To ensure that every graph is connected, we first created a tree with all vertices and then added the remaining edges at random. Our experiments ran on an Intel®

<span id="page-12-0"></span>Table 1: Experimental results on two datasets. The mean  $\mu$  is relative to Praline (abbreviated Pral);  $\beta$  measures the percentage of cases where an algorithm achieved the best result. Sums over 100 % are possible due to ties.

(a) The Internet Topology Zoo benchmark set.

|                      | Force |           | Hybrid1 |         | Hybrid2 |           | Hola  |         | Pral. |         |
|----------------------|-------|-----------|---------|---------|---------|-----------|-------|---------|-------|---------|
|                      | $\mu$ | $\beta$   | $\mu$   | $\beta$ | $\mu$   | $\beta$   | $\mu$ | $\beta$ | $\mu$ | $\beta$ |
| crossings            | 3.90  | 27        | 1.30    | 54      | 1.00    | 70        | .85   | 77      | 1     | 70      |
| edge bends           | .92   | 4         | .76     | 6       | .49     | 51        | .50   | 47      | 1     | 2       |
| edge length variance | .47   | <b>39</b> | .39     | 21      | .37     | 38        | 11.43 | 3       | 1     | 1       |
| total edge length    | .73   | 20        | .61     | 6       | .49     | <b>73</b> | 1.83  | 0       | 1     | 2       |
| bounding box area    | .68   | 30        | .56     | 32      | .56     | <b>38</b> | 3.94  | 0       | 1     | 0       |
| aspect ratio         | .93   | 35        | 1.03    | 14      | 1.07    | 11        | 1.35  | 22      | 1     | 18      |
| $\delta_{\min}$      | 1.11  | 88        | 1.10    | 87      | 1.10    | 87        | 1.01  | 45      | 1     | 69      |

(b) The Pseudo-cableplans benchmark set.

|                      | Force |           | Hybrid1 |         | Hybrid2 |         | Hola  |         | Pral. |         |
|----------------------|-------|-----------|---------|---------|---------|---------|-------|---------|-------|---------|
|                      | $\mu$ | $\beta$   | $\mu$   | $\beta$ | $\mu$   | $\beta$ | $\mu$ | $\beta$ | $\mu$ | $\beta$ |
| crossings            | 1.58  | 9         | 1.03    | 19      | 1.00    | 25      | .73   | 89      | 1     | 25      |
| edge bends           | .96   | 1         | .76     | 2       | .66     | 12      | .30   | 88      | 1     | 1       |
| edge length variance | .34   | $\bf 52$  | .35     | 31      | .40     | 19      | 1.79  | 0       | 1     | 0       |
| total edge length    | .59   | 29        | .52     | 29      | .54     | 43      | 1.20  | 0       | 1     | 0       |
| bounding box area    | .55   | 25        | .50     | 24      | .50     | 51      | 2.21  | 0       | 1     | 0       |
| aspect ratio         | .99   | <b>37</b> | .97     | 12      | .96     | 17      | .97   | 24      | 1     | 10      |
| $\delta_{\min}$      | 1.42  | 93        | 1.42    | 93      | 1.42    | 93      | 1.24  | 60      | 1     | 33      |

 $Core^{TM}$  i7-8565U. We measured runtimes using Java's nanoTime function (for our pipeline and Praline) and the GNU time command (for Hola).

See Fig. 9 for different steps of our pipeline. Steps that consistently require less than 10 ms to complete are omitted. The overall runtime is clearly dominated by edge routing and crossing reduction (that is, finding pairs of edges that cross more than once and then joining their common subpaths), followed by force-directed vertex layout. The time spent on nudging, edge ordering, and on creating the routing graph was insignificant.

The time for drawing the graphs from the two benchmark sets is shown in Fig. 10. The Hybrid setups are omitted. In Hybrid just like with Force the edge routing dominates the runtime, in Hybrid the runtime is dominated by performing the Praline layout. Note that Praline by default does ten repetitions with different initial vertex positions of which it keeps the best. Depicted is the sum of all repetitions. For Praline and Force only the bare layouting time was measured whereas for Hola, for technical reasons, the measurements include file handling. However, this increases the runtime by less than 50 ms.

<span id="page-13-0"></span>![](_page_13_Figure_0.jpeg)

Fig. 8: Selected metrics of Hola , and Hybrid2 relative to Praline.

## 4 Conclusions

Our experiments show that Hybrid1 is a good allrounder. The edge nudging step performs particularly well and leads to compact drawings. On the other hand, due to our current rather simple edge routing, the drawings tend to have more bends and crossings than those of its competitors. When combined with a more sophisticated layouting (the Hybrid2 setup), we can significantly improve compactness (almost half the bounding box area) and number of edge bends with the same number of crossings as Praline.

Nonetheless, we intend to improve edge routing, especially in terms of crossings. To this end, Wybrow et al. [\[20\]](#page-16-4) suggested to take into account edges that have already been routed. Also it may help to reorder the ports around the boundary of the vertex boxes. To reduce the number of bends, we want to add a postprocessing that straightens Z-shaped edges whose middle piece is short. Currently, such unnecessary double bends tend to occur quite frequently; see Fig. [11b.](#page-15-0)

<span id="page-14-3"></span>![](_page_14_Figure_0.jpeg)

Fig. 9: Running times of the FORCE pipeline on random multigraphs with an average vertex degree of 4. Stages with less than 10 ms average running time are omitted.

<span id="page-14-4"></span>![](_page_14_Figure_2.jpeg)

Fig. 10: Running times of Force ♠, Hola ♠, and Praline ● for our benchmark sets.

**Acknowledgments.** We thank Steve Kieffer, Micheal Wybrow, and Tobias Czauderna who helped us with Hola in our experiments, Johannes Zink who helped us with Praline, and our very supportive reviewers. This work was supported by BMBF grant 01IS22012C.

#### References

- <span id="page-14-0"></span>T. C. Biedl, B. Madden, and I. G. Tollis. The three-phase method: A unified approach to orthogonal graph drawing. *Int. J. Comput. Geom. Appl.*, 10(6):553–580, 2000. doi:10.1142/S0218195900000310.
- <span id="page-14-2"></span>2. C. Binucci, W. Didimo, G. Liotta, and M. Nonato. Orthogonal drawings of graphs with vertex and edge labels. *Comput. Geom. Theory Appl.*, 32(2):71–114, 2005. doi:10.1016/j.comgeo.2005.02.001.
- <span id="page-14-1"></span>3. T. Dwyer, Y. Koren, and K. Marriott. IPSep-CoLa: An incremental procedure for separation constraint layout of graphs. *IEEE Trans. Visual. Comput. Graphics*, 12(5):821–828, 2006. doi:10.1109/TVCG.2006.156.

<span id="page-15-0"></span>![](_page_15_Figure_0.jpeg)

Fig. 11: An example from the Internet Topology Zoo drawn by the five layout algorithms. The figures are scaled proportionally. The numbers refer to: crossings, bends, δmin (in pixels), and area (in percent w.r.t. Praline).

- <span id="page-16-17"></span>4. T. Dwyer, B. Lee, D. Fisher, K. I. Quinn, P. Isenberg, G. Robertson, and C. North. A comparison of user-generated and automatic graph layouts. IEEE Trans. Visual. Comput. Graphics, 15(6):961–968, 2009. [doi:10.1109/TVCG.2009.109](https://doi.org/10.1109/TVCG.2009.109).
- <span id="page-16-2"></span>5. T. Dwyer, K. Marriott, and P. J. Stuckey. Fast node overlap removal. In Graph Drawing, volume 3843 of LNCS, pages 153–164. Springer, 2006. [doi:10.1007/](https://doi.org/10.1007/11618058_15) [11618058\\_15](https://doi.org/10.1007/11618058_15).
- <span id="page-16-10"></span>6. T. M. J. Fruchterman and E. M. Reingold. Graph drawing by force-directed placement. Softw. Pract. & Exper., 21(11):1129–1164, 1991. [doi:10.1002/spe.](https://doi.org/10.1002/spe.4380211102) [4380211102](https://doi.org/10.1002/spe.4380211102).
- <span id="page-16-12"></span>7. P. Groeneveld. Wire ordering for detailed routing. IEEE Design & Test Comput., 6(6):6–17, 1989. [doi:10.1109/54.41670](https://doi.org/10.1109/54.41670).
- <span id="page-16-5"></span>8. S. Kieffer, T. Dwyer, K. Marriott, and M. Wybrow. HOLA: Human-like orthogonal network layout. IEEE Trans. Visual. Comput. Graphics, 22(1):349–358, 2016. [doi:](https://doi.org/10.1109/TVCG.2015.2467451) [10.1109/TVCG.2015.2467451](https://doi.org/10.1109/TVCG.2015.2467451).
- <span id="page-16-15"></span>9. S. Knight, H. X. Nguyen, N. Falkner, R. Bowden, and M. Roughan. The internet topology zoo. IEEE J. Selected Areas Comm., 29(9):1765–1775, 2011. [doi:10.](https://doi.org/10.1109/JSAC.2011.111002) [1109/JSAC.2011.111002](https://doi.org/10.1109/JSAC.2011.111002).
- <span id="page-16-1"></span>10. T. Lengauer. Combinatorial Algorithms for Integrated Circuit Layout. Vieweg+Teubner, 1990. [doi:10.1007/978-3-322-92106-2](https://doi.org/10.1007/978-3-322-92106-2).
- <span id="page-16-11"></span>11. L. Nachmanson, A. Nocaj, S. Bereg, L. Zhang, and A. Holroyd. Node overlap removal by growing a tree. J. Graph Alg. Appl., 21(5):857–872, 2017. [doi:10.](https://doi.org/10.7155/jgaa.00442) [7155/jgaa.00442](https://doi.org/10.7155/jgaa.00442).
- <span id="page-16-13"></span>12. M. Nöllenburg. An improved algorithm for the metro-line crossing minimization problem. In Graph Drawing, volume 5849 of LNCS, pages 381–392. Springer, 2010. [doi:10.1007/978-3-642-11805-0\\_36](https://doi.org/10.1007/978-3-642-11805-0_36).
- <span id="page-16-14"></span>13. S. Pupyrev, L. Nachmanson, S. Bereg, and A. E. Holroyd. Edge routing with ordered bundles. Comput. Geom. Theory Appl., 52:18–33, 2016. [doi:10.1016/j.](https://doi.org/10.1016/j.comgeo.2015.10.005) [comgeo.2015.10.005](https://doi.org/10.1016/j.comgeo.2015.10.005).
- <span id="page-16-16"></span>14. H. Purchase. Effective information visualisation: a study of graph drawing aesthetics and algorithms. Interacting with Computers, 13(2):147–162, 2000. [doi:](https://doi.org/10.1016/S0953-5438(00)00032-1) [10.1016/S0953-5438\(00\)00032-1](https://doi.org/10.1016/S0953-5438(00)00032-1).
- <span id="page-16-7"></span>15. Real-Time and Embedded Systems group. Kiel Integrated Environment for Layout Eclipse Rich Client (KIELER), 2020. URL: [https://rtsys.informatik.](https://rtsys.informatik.uni-kiel.de/confluence/display/KIELER/Overview) [uni-kiel.de/confluence/display/KIELER/Overview](https://rtsys.informatik.uni-kiel.de/confluence/display/KIELER/Overview).
- <span id="page-16-3"></span>16. U. Rüegg, S. Kieffer, T. Dwyer, K. Marriott, and M. Wybrow. Stress-minimizing orthogonal layout of data flow diagrams with ports. In Graph Drawing, volume 8871 of LNCS, pages 319–330. Springer, 2014. [doi:10.1007/978-3-662-45803-7\\_27](https://doi.org/10.1007/978-3-662-45803-7_27).
- <span id="page-16-6"></span>17. C. D. Schulze, M. Spönemann, and R. von Hanxleden. Drawing layered graphs with port constraints. J. Vis. Lang. Comput., 25(2):89–106, 2014. [doi:10.1016/](https://doi.org/10.1016/j.jvlc.2013.11.005) [j.jvlc.2013.11.005](https://doi.org/10.1016/j.jvlc.2013.11.005).
- <span id="page-16-9"></span>18. K. Sugiyama, S. Tagawa, and M. Toda. Methods for visual understanding of hierarchical system structures. IEEE Trans. Syst. Man Cybern., 11(2):109–125, 1981. [doi:10.1109/TSMC.1981.4308636](https://doi.org/10.1109/TSMC.1981.4308636).
- <span id="page-16-0"></span>19. R. Tamassia. On embedding a graph in the grid with the minimum number of bends. SIAM J. Comput., 16(3):421–444, 1987. [doi:10.1137/0216030](https://doi.org/10.1137/0216030).
- <span id="page-16-4"></span>20. M. Wybrow, K. Marriott, and P. J. Stuckey. Orthogonal connector routing. In Graph Drawing, volume 5849 of LNCS, pages 219–231. Springer, 2010. [doi:10.](https://doi.org/10.1007/978-3-642-11805-0_22) [1007/978-3-642-11805-0\\_22](https://doi.org/10.1007/978-3-642-11805-0_22).
- <span id="page-16-8"></span>21. J. Zink, J. Walter, J. Baumeister, and A. Wolff. Layered drawing of undirected graphs with generalized port constraints. Comput. Geom. Theory Appl., 105– 106(101886):1–29, 2022. [doi:10.1016/j.comgeo.2022.101886](https://doi.org/10.1016/j.comgeo.2022.101886).