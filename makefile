
.PHONY: all clean
all:
	colcon build --symlink

clean:
	-rm -rf build install log 