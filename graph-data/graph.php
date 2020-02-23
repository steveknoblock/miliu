<?php

/* Expected data model

edges
-----
source_id  <-- source of the arc
dest_id    <-- target of the arc
position   <-- ordered pairs
updated
state

The edges table consists of rows representing single one-directional arcs or arrows of the graph. The graph defined by and contained by this table will
be a complete symmetrical graph, which simply means for each arc between nodes going in one direction a reverse arc going in the opposite direction will be generated when adding edges to the table.


following
followed by


*/

class Edge {

	protected $source_id;
	protected $dest_id;
	protected $position;
	protected $updated;
	protected $state;

	public function __construct($source_id, $dest_id) {
		$this->source_id = $source_id;
		$this->dest_id = $dest_id;

	}

	function public sourceId($val) {
		$this->prop('source_id', $val);
	}

	function public destId($val) {
		$this->prop('source_id', $val);
	}

	function public position($val) {
		$this->prop('position', $val);
	}

	function protected prop($key, $val=null) {
		if($val) {
			$this->key = $val;
		} else {
			return $this->key;
		}
	}

}

/* graphs are given particular meanings, such as follower graphs, or content graphs 
	RDF dervived graphs try to particularize graphs by including the meaning
*/
class Graph {
	protected $edges;

	public function followers($source_id) {

	}
}
